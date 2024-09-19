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
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import boto3
import json
import watchtower  # Added for CloudWatch logging
from botocore.exceptions import ClientError
from streamlit.components.v1 import html

# Utility functions from your backend
from utils import bedrock

# Set up logging with CloudWatch handler
session = boto3.Session()
log_group = "CodeConverterLogs"  # Name your CloudWatch log group
log_stream = os.environ.get('INSTANCE_ID', 'local')  # Use instance/container ID or default to 'local'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create the CloudWatch client
cloudwatch_client = session.client('logs')

# Set up CloudWatch handler (no boto3_session argument, using the client)
cloudwatch_handler = watchtower.CloudWatchLogHandler(
    log_group=log_group,
    stream_name=log_stream,
    boto3_client=cloudwatch_client  # Correct client parameter
)
logging.getLogger().addHandler(cloudwatch_handler)

# Streamlit UI logs will also be sent to CloudWatch
st_logger = logging.getLogger('streamlit')
st_logger.setLevel(logging.INFO)
st_logger.addHandler(cloudwatch_handler)

# Set page configuration
st.set_page_config(page_title="Code Converter", page_icon=":gear:", layout="wide")

# Custom CSS for styling
st.markdown("""
    <style>
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #45a049;
        }
        .stProgress > div > div {
            background-color: #4CAF50;
        }
        .header {
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 20px;
        }
        .dropdown {
            border-radius: 8px;
            padding: 8px;
            border: 1px solid #ccc;
            margin-bottom: 10px;
        }
        .loading-icon {
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
""", unsafe_allow_html=True)

# AWS session and clients
try:
    s3_client = session.client('s3')
    bedrock_runtime = session.client('bedrock-runtime')
except ClientError as e:
    logging.error(f"Error creating AWS session or clients: {e}")
    st.error(f"Error creating AWS session or clients: {e}")
    st.stop()

# Supported programming languages and their file extensions
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

def list_s3_buckets():
    try:
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        return buckets
    except ClientError as e:
        logging.error(f"Error listing buckets: {e}")
        st.error(f"Error listing buckets: {e}")
        return []

def get_matching_files(bucket, prefix, extension):
    matching_files = []
    continuation_token = None

    while True:
        try:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=bucket, Prefix=prefix, ContinuationToken=continuation_token)
            else:
                response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith(extension):
                        matching_files.append(obj['Key'])

            if response.get('NextContinuationToken'):
                continuation_token = response['NextContinuationToken']
            else:
                break
        except ClientError as e:
            logging.error(f"Error fetching files from bucket {bucket}: {e}")
            st.error(f"Error fetching files from bucket {bucket}: {e}")
            return []

    return matching_files

def convert_file(source_bucket, target_bucket, file_key, source_language, target_language):
    logging.info(f"Starting conversion for file: {file_key}")
    source_extension = language_extensions[source_language]
    target_extension = language_extensions[target_language]

    try:
        response = s3_client.get_object(Bucket=source_bucket, Key=file_key)
        source_code = response['Body'].read().decode('utf-8')
    except ClientError as e:
        logging.error(f"Error fetching file {file_key} from bucket {source_bucket}: {e}")
        st.error(f"Error fetching file {file_key} from bucket {source_bucket}: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error reading file {file_key}: {e}")
        st.error(f"Unexpected error reading file {file_key}: {e}")
        return False

    # Conversion logic
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Replace with your actual model ID
    max_tokens = 1000  # Adjust as necessary
    system = "You are a highly knowledgeable and efficient code conversion assistant. Your task is to accurately and contextually convert source code from one programming language to another, maintaining the structure, logic, and functionality of the original code. Ensure that the converted code adheres to best practices in the target language, optimizing for readability and performance."

    user_message = {"role": "user", "content": f"<source_code> {source_code} </source_code> Convert the source code from {source_language} to {target_language}. Put the response in <target_code> </target_code>"}
    messages = [user_message]
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages
    })

    try:
        response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
        result = json.loads(response['body'].read().decode('utf-8'))

        target_code_with_blocks = result['content'][0]['text']
        target_code = target_code_with_blocks.replace('<target_code>', '').replace('</target_code>', '')

        target_key = f"{os.path.splitext(file_key)[0]}{target_extension}"
        s3_client.put_object(Bucket=target_bucket, Key=target_key, Body=target_code.encode('utf-8'))
        logging.info(f"Converted {file_key} to {target_key}")
        return True
    except ClientError as e:
        logging.error(f"Error converting file {file_key}: {e}")
        st.error(f"Error converting file {file_key}: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during conversion of file {file_key}: {e}")
        st.error(f"Unexpected error during conversion of file {file_key}: {e}")
        return False

def convert_files(source_bucket, target_bucket, prefix, source_language, target_language, parallel=False, max_workers=4):
    source_extension = language_extensions[source_language]
    matching_files = get_matching_files(source_bucket, prefix, source_extension)

    if not matching_files:
        logging.warning(f"No files with the '{source_extension}' extension found in bucket '{source_bucket}' with prefix '{prefix}'.")
        st.warning(f"No files with the '{source_extension}' extension found in bucket '{source_bucket}' with prefix '{prefix}'.")
        return False

    logging.info(f"Found {len(matching_files)} files to convert.")
    st.info(f"Found {len(matching_files)} files to convert.")

    progress_bar = st.progress(0)
    success = False

    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(
                lambda file_key: convert_file(source_bucket, target_bucket, file_key, source_language, target_language),
                matching_files))
            for i, result in enumerate(results):
                progress_bar.progress((i + 1) / len(matching_files))
    else:
        results = []
        for i, file_key in enumerate(matching_files):
            result = convert_file(source_bucket, target_bucket, file_key, source_language, target_language)
            results.append(result)
            progress_bar.progress((i + 1) / len(matching_files))

    success = any(results)

    if success:
        logging.info(f"Successfully converted files from '{source_language}' to '{target_language}'.")
        st.success(f"Successfully converted files from '{source_language}' to '{target_language}'.")
    else:
        logging.error(f"Failed to convert files from '{source_language}' to '{target_language}'.")
        st.error(f"Failed to convert files from '{source_language}' to '{target_language}'.")

# Main Streamlit application UI
st.title("Code Converter - Using Amazon Bedrock")
st.markdown("<div class='header'>Convert code between programming languages</div>", unsafe_allow_html=True)

buckets = list_s3_buckets()
source_bucket = st.selectbox("Select the source S3 bucket:", buckets, key="source_bucket", help="Select the S3 bucket where the files are stored.")
target_bucket = st.selectbox("Select the target S3 bucket:", buckets, key="target_bucket", help="Select the S3 bucket where the converted files will be stored.")

prefix = st.text_input("Enter the prefix for the files (optional):", value="", key="prefix")
source_language = st.selectbox("Select the source programming language:", supported_languages, key="source_language")
target_language = st.selectbox("Select the target programming language:", supported_languages, key="target_language")

parallel_processing = st.checkbox("Use parallel processing", value=False, key="parallel")
max_workers = st.slider("Select maximum workers for parallel processing:", min_value=1, max_value=10, value=4, key="max_workers")

if st.button("Convert Files"):
    with st.spinner('Processing...'):
        if source_bucket and target_bucket and source_language and target_language:
            convert_files(source_bucket, target_bucket, prefix, source_language, target_language, parallel=parallel_processing, max_workers=max_workers)
        else:
            st.error("Please select both source and target buckets and languages.")
