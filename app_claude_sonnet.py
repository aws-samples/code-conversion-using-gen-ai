''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
'''

import os
import logging
import re
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import boto3
import json
import watchtower
from botocore.exceptions import ClientError
import time
import random
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx
from utils import bedrock

# Set up logging with CloudWatch handler
session = boto3.Session()
log_group = "CodeConverterLogs"
log_stream = os.environ.get('INSTANCE_ID', 'local')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
cloudwatch_client = session.client('logs')
cloudwatch_handler = watchtower.CloudWatchLogHandler(
    log_group=log_group,
    stream_name=log_stream,
    boto3_client=cloudwatch_client
)
logging.getLogger().addHandler(cloudwatch_handler)

# Streamlit UI logs will also be sent to CloudWatch
st_logger = logging.getLogger('streamlit')
st_logger.setLevel(logging.INFO)
st_logger.addHandler(cloudwatch_handler)

# Set page configuration
st.set_page_config(page_title="Code Converter", page_icon=":gear:", layout="wide")

# AWS session and clients
try:
    s3_client = session.client('s3')
    bedrock_runtime = session.client('bedrock-runtime')
except ClientError as e:
    logging.error(f"Error creating AWS session or clients: {e}")
    st.error(f"Error creating AWS session or clients: {e}")
    st.stop()

language_extensions = {
    "Python": ".py",
    "Java": ".java",
    "JavaScript": ".js",
    "C++": ".cpp",
    "C#": ".cs",
    "Go": ".go",
    "Scala": ".scala",
    "PHP": ".php",
    "R": ".r",
    "Bash": ".sh",
    "PowerShell": ".ps1",
    "SQL": ".sql",
    "HTML": ".html",
    "CSS": ".css",
    "TypeScript": ".ts",
    "Objective-C": ".m"
}

supported_languages = list(language_extensions.keys())

# Claude model configurations
CLAUDE_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
CLAUDE_VERSION = "bedrock-2023-05-31"

OVERLAP_LINES = 5
MAX_CHUNK_SIZE = 4096

def get_matching_files(bucket, prefix, extension):
    matching_files = []
    continuation_token = None
    while True:
        try:
            response = (s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, ContinuationToken=continuation_token)
                        if continuation_token else s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix))
            if 'Contents' in response:
                matching_files.extend(
                    [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith(extension)]
                )
            if response.get('NextContinuationToken'):
                continuation_token = response['NextContinuationToken']
            else:
                break
        except ClientError as e:
            logging.error(f"Error fetching files from bucket {bucket}: {e}")
            st.error(f"Error fetching files from bucket {bucket}: {e}")
            return []
    return matching_files

def chunk_code(source_code, max_chunk_size=MAX_CHUNK_SIZE, overlap_lines=OVERLAP_LINES):
    lines = source_code.splitlines()
    chunks = []
    start = 0
    while start < len(lines):
        current_chunk = []
        current_length = 0
        i = start
        while i < len(lines) and current_length + len(lines[i]) + 1 <= max_chunk_size:
            current_chunk.append(lines[i])
            current_length += len(lines[i]) + 1
            i += 1
        chunks.append("\n".join(current_chunk))
        if i >= len(lines):
            break
        start = max(0, i - overlap_lines)
    return chunks

def merge_converted_chunks(converted_chunks, overlap_lines=OVERLAP_LINES):
    if not converted_chunks:
        return ""
    merged = converted_chunks[0]
    for chunk in converted_chunks[1:]:
        chunk_lines = chunk.splitlines()
        merged_lines = merged.splitlines()
        if len(chunk_lines) >= overlap_lines and len(merged_lines) >= overlap_lines:
            if chunk_lines[:overlap_lines] == merged_lines[-overlap_lines:]:
                merged += "\n" + "\n".join(chunk_lines[overlap_lines:])
            else:
                merged += "\n" + "\n".join(chunk_lines)
        else:
            merged += "\n" + "\n".join(chunk_lines)
    return merged

def convert_chunk(chunk, source_language, target_language):
    """Convert a chunk of code using Claude on Bedrock.
    
    Args:
        chunk: The code chunk to convert
        source_language: The source programming language
        target_language: The target programming language
    """
    model_id = CLAUDE_MODEL_ID
    
    # Claude prompt structure
    system_prompt = ("You are a code conversion assistant. Convert source code accurately while preserving "
                 "structure and logic. Output only the converted code without explanations. "
                 "Ensure that the converted code adheres to best practices in the target language, "
                 "optimizing for readability and performance. Be concise. Do not add any extra explanation "
                 "or formatting markers.")
    
    user_prompt = f"<source_code>\n{chunk}\n</source_code>\n\nConvert this code from {source_language} to {target_language}. Provide only the converted code without explanations or markdown formatting."
    
    # Claude request structure for Bedrock
    request_body = {
        "anthropic_version": CLAUDE_VERSION,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "system": system_prompt
    }
    
    attempt = 0
    max_retries = 5
    while attempt < max_retries:
        try:
            # Prepare invoke model parameters - using direct invocation
            response = bedrock_runtime.invoke_model(
                body=json.dumps(request_body),
                modelId=model_id,
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read().decode('utf-8'))
            # Correctly access Claude's response structure
            converted = response_body["content"][0]["text"]
            
            # Clean up any code block formatting that Claude might add
            converted = re.sub(r'```[a-zA-Z]*', '', converted)
            converted = converted.replace('```', '').strip()
            
            return converted
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e).lower()
            
            if error_code == 'ThrottlingException':
                attempt += 1
                delay = min(60, 5 * (2 ** (attempt - 1))) + random.uniform(0, 1)
                logging.warning(f"Throttling occurred converting chunk. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            elif error_code == 'ValidationException' and ('inference profile' in error_message or 
                                    'through put' in error_message or 'throughput' in error_message):
                logging.error("Model requires provisioned throughput or inference profile.")
                logging.error("Please see AWS Bedrock documentation to set up the model correctly.")
                return None
            elif error_code == 'AccessDeniedException':
                logging.error("Access denied to the model. Check your AWS permissions.")
                return None
            elif error_code == 'ModelNotReadyException':
                logging.error("Model is not ready or available in your region.")
                return None
            else:
                logging.error(f"Error converting chunk: {e}")
                return None
        except Exception as e:
            logging.error(f"Unexpected error converting chunk: {e}")
            return None
    return None

def convert_file(source_bucket, target_bucket, file_key, source_language, target_language, update_ui=True):
    logging.info(f"Starting conversion for file: {file_key}")
    if update_ui:
        alert = st.info(f"Converting - {file_key}")
    target_extension = language_extensions[target_language]
    try:
        response = s3_client.get_object(Bucket=source_bucket, Key=file_key)
        source_code = response['Body'].read().decode('utf-8')
    except ClientError as e:
        logging.error(f"Error fetching file {file_key} from bucket {source_bucket}: {e}")
        if update_ui:
            st.error(f"Error fetching file {file_key} from bucket {source_bucket}: {e}")
        return False
    code_chunks = chunk_code(source_code)
    total_chunks = len(code_chunks)
    if update_ui:
        st.write(f"File `{file_key}` split into **{total_chunks} chunks**.")
        chunk_progress = st.progress(0)
        converted_chunks = []
        for idx, chunk in enumerate(code_chunks):
            st.write(f"Processing chunk **{idx+1}/{total_chunks}** for file `{file_key}`...")
            converted_chunk = convert_chunk(chunk, source_language, target_language)
            if converted_chunk is None:
                st.error(f"Conversion failed for chunk {idx+1} of file `{file_key}`.")
                return False
            converted_chunks.append(converted_chunk)
            chunk_progress.progress((idx + 1) / total_chunks)
    else:
        converted_chunks = [None] * total_chunks
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_index = {executor.submit(convert_chunk, chunk, source_language, target_language): idx
                               for idx, chunk in enumerate(code_chunks)}
            for future in future_to_index:
                idx = future_to_index[future]
                result = future.result()
                if result is None:
                    logging.error(f"Conversion failed for chunk {idx+1} of file `{file_key}` in parallel processing.")
                    return False
                converted_chunks[idx] = result
    final_converted = merge_converted_chunks(converted_chunks)
    target_key = f"{os.path.splitext(file_key)[0]}{target_extension}"
    try:
        s3_client.put_object(Bucket=target_bucket, Key=target_key, Body=final_converted.encode('utf-8'))
        logging.info(f"Converted {file_key} to {target_key}")
    except ClientError as e:
        logging.error(f"Error uploading converted file {target_key}: {e}")
        if update_ui:
            st.error(f"Error uploading converted file {target_key}: {e}")
        return False
    if update_ui:
        alert.empty()
    return True

def parallel_convert_file(file_key, source_bucket, target_bucket, source_language, target_language):
    add_script_run_ctx(threading.current_thread())
    return convert_file(source_bucket, target_bucket, file_key, source_language, target_language, update_ui=False)

def convert_files(source_bucket, target_bucket, prefix, source_language, target_language, parallel=False, max_workers=4):
    source_extension = language_extensions[source_language]
    matching_files = get_matching_files(source_bucket, prefix, source_extension)
    if not matching_files:
        st.warning(f"No files found in '{source_bucket}' with prefix '{prefix}'.")
        return
    
    st.info(f"Found {len(matching_files)} files to convert.")
    
    # Show information about potential requirements
    with st.expander("Important: AWS Bedrock Model Requirements"):
        st.markdown("""
        ### Using Claude 3.7 Sonnet on Bedrock
        
        To use this code converter:
        
        1. Your AWS account must have access to the Claude 3.7 Sonnet model on Bedrock
        2. You might need to set up provisioned throughput for the model in the AWS console
        3. If you encounter errors about "inference profiles" or "throughput", please see the 
           [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-throughput.html) 
           for information on setting up the required resources
        
        For enterprise accounts, you may need to work with your AWS administrator to set up the appropriate throughput configuration.
        """)
    
    file_progress = st.progress(0)
    if parallel:
        st.write(f"Running in **Parallel Mode** with up to {max_workers} workers.")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(
                lambda f: parallel_convert_file(f, source_bucket, target_bucket, source_language, target_language),
                matching_files
            ))
            for i, _ in enumerate(results):
                file_progress.progress((i + 1) / len(matching_files))
    else:
        st.write(f"Running in **Sequential Mode**.")
        for i, file_key in enumerate(matching_files):
            success = convert_file(source_bucket, target_bucket, file_key, source_language, target_language, update_ui=True)
            if not success:
                st.error(f"Conversion failed for file `{file_key}`.")
            file_progress.progress((i + 1) / len(matching_files))
    st.success("Conversion process completed.")

# Check if Bedrock foundation models are available
def get_available_bedrock_models():
    try:
        response = bedrock_runtime.list_foundation_models()
        return [model['modelId'] for model in response.get('modelSummaries', [])]
    except Exception as e:
        logging.warning(f"Could not fetch available Bedrock models: {e}")
        return []

# Streamlit UI
st.title("Code Converter - Using Claude 3.7 Sonnet")
st.write("This application converts code between programming languages using Amazon Bedrock and Claude 3.7 Sonnet.")

# Show a message about Bedrock setup
st.info("""
This application uses Amazon Bedrock with Claude 3.7 Sonnet. To use this application:

1. Your AWS account needs access to Claude 3.7 Sonnet on Amazon Bedrock
2. You may need to set up model throughput in the AWS console depending on your account type
3. Make sure your AWS credentials have the necessary permissions
""")

# Main application UI
buckets = [b['Name'] for b in s3_client.list_buckets().get('Buckets', [])]
source_bucket = st.selectbox("Select the source S3 bucket:", buckets, key="source_bucket")
target_bucket = st.selectbox("Select the target S3 bucket:", buckets, key="target_bucket")
prefix = st.text_input("Enter the prefix for the files:", key="prefix")
source_language = st.selectbox("Select the source language:", supported_languages, key="source_language")
target_language = st.selectbox("Select the target language:", supported_languages, key="target_language")
parallel_processing = st.checkbox("Use parallel processing", key="parallel")
max_workers = st.slider("Max workers:", 1, 10, 4, key="max_workers")

if st.button("Convert Files"):
    convert_files(source_bucket, target_bucket, prefix, source_language, target_language, 
                 parallel_processing, max_workers)