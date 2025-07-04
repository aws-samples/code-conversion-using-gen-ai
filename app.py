''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
'''

# IMPORTANT: set_page_config MUST be the first Streamlit command
import streamlit as st

st.set_page_config(
    page_title="Gen AI Code Converter with AI Tests",
    page_icon="🤖",
    layout="wide"
)

# Now import everything else
import os
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

from utils import bedrock
from utils.file_converter import BULK_CONVERSION_LANGUAGES, CONVERSION_TEMPLATES
from utils.workflow_orchestrator import GenAIWorkflowOrchestrator, display_workflow_summary

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize AWS clients
def get_aws_clients():
    """Initialize AWS clients"""
    try:
        s3_client = boto3.client('s3')
        bedrock_runtime = bedrock.get_bedrock_client()
        return s3_client, bedrock_runtime
    except Exception as e:
        st.error(f"Error initializing AWS clients: {e}")
        st.stop()

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'matching_files' not in st.session_state:
        st.session_state.matching_files = []
    if 'workflow_results' not in st.session_state:
        st.session_state.workflow_results = []
    if 'conversion_in_progress' not in st.session_state:
        st.session_state.conversion_in_progress = False

def scan_s3_bucket_for_files(s3_client, bucket_name, prefix="", file_extension=""):
    """Scan entire S3 bucket for files with specific extension"""
    matching_files = []
    
    # Create a progress placeholder
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        total_objects = 0
        matching_count = 0
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    total_objects += 1
                    file_key = obj['Key']
                    
                    # Update status every 100 files
                    if total_objects % 100 == 0:
                        status_placeholder.info(f"🔍 Scanning... Found {matching_count} matching files out of {total_objects} total objects")
                    
                    # Check if file matches the extension
                    if file_extension and file_key.lower().endswith(file_extension.lower()):
                        matching_files.append({
                            'key': file_key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'size_kb': round(obj['Size'] / 1024, 2)
                        })
                        matching_count += 1
                    elif not file_extension:  # If no extension specified, include all files
                        matching_files.append({
                            'key': file_key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'size_kb': round(obj['Size'] / 1024, 2)
                        })
                        matching_count += 1
        
        # Final status
        status_placeholder.success(f"✅ Scan complete! Found {matching_count} matching files out of {total_objects} total objects")
        progress_placeholder.empty()
        
    except ClientError as e:
        st.error(f"Error scanning S3 bucket {bucket_name}: {e}")
        return []
    except Exception as e:
        st.error(f"Unexpected error scanning bucket: {e}")
        return []
    
    return matching_files

def get_template_info(template_name):
    """Get template information"""
    if template_name in CONVERSION_TEMPLATES:
        return CONVERSION_TEMPLATES[template_name]
    return None

def process_files_with_enhanced_genai_workflow(orchestrator, matching_files, source_bucket, target_bucket,
                                             source_language, target_language, template_name,
                                             custom_source_pattern, custom_target_pattern, use_parallel, max_workers):
    """Process files using the Gen AI workflow with AI test generation"""
    
    st.subheader("🤖 Gen AI Workflow with AI Test Generation")
    st.write("**4-Phase AI Workflow**: Analysis → Conversion → Validation → AI Test Generation")
    
    # Overall progress tracking
    total_files = len(matching_files)
    overall_progress = st.progress(0)
    overall_status = st.empty()
    
    # Phase indicators
    st.write("**Processing Phases:**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.write("🔍 **Phase 1**: AI Analysis")
    with col2:
        st.write("🔄 **Phase 2**: AI Conversion")
    with col3:
        st.write("✅ **Phase 3**: AI Validation")
    with col4:
        st.write("🧪 **Phase 4**: AI Test Generation")
    
    # Results tracking
    workflow_results = []
    start_time = time.time()
    
    # Process files sequentially to avoid UI issues
    st.info(f"🔄 Processing {total_files} files sequentially with AI workflow...")
    
    for i, file_info in enumerate(matching_files):
        overall_status.info(f"🤖 Processing file {i+1}/{total_files}: {file_info['key']}")
        
        # Create a container for this file's processing
        file_container = st.container()
        
        with file_container:
            # Process single file through complete enhanced AI workflow
            result = orchestrator.process_file_complete_workflow(
                file_info, source_bucket, target_bucket, source_language, target_language,
                template_name, custom_source_pattern, custom_target_pattern
            )
            
            workflow_results.append(result)
        
        # Update overall progress
        progress = (i + 1) / total_files
        overall_progress.progress(progress)
        
        # Calculate and display metrics
        elapsed_time = time.time() - start_time
        avg_time_per_file = elapsed_time / (i + 1)
        remaining_time = (total_files - i - 1) * avg_time_per_file
        
        successful_so_far = len([r for r in workflow_results if r['success']])
        total_tokens_so_far = sum(r['total_tokens_used'] for r in workflow_results)
        total_cost_so_far = sum(r['total_cost'] for r in workflow_results)
        test_files_so_far = len([r for r in workflow_results if r.get('test_file_key') or r.get('test_file_path')])
        
        overall_status.info(
            f"📊 Progress: {i+1}/{total_files} | "
            f"✅ Success: {successful_so_far} | "
            f"🧪 Tests: {test_files_so_far} | "
            f"🤖 Tokens: {total_tokens_so_far:,} | "
            f"💰 Cost: ${total_cost_so_far:.3f} | "
            f"⏱️ Est. remaining: {remaining_time/60:.1f} min"
        )
        
        # Small delay to show progress
        time.sleep(0.1)
    
    # Store results in session state
    st.session_state.workflow_results = workflow_results
    
    # Final summary
    total_time = time.time() - start_time
    successful_files = len([r for r in workflow_results if r['success']])
    total_test_files = len([r for r in workflow_results if r.get('test_file_key') or r.get('test_file_path')])
    
    overall_status.success(
        f"🎉 **Gen AI Workflow Complete!** "
        f"✅ {successful_files}/{total_files} files processed successfully "
        f"🧪 {total_test_files} test files generated "
        f"in {total_time/60:.1f} minutes"
    )
    
    # Display comprehensive results
    display_workflow_summary(workflow_results)
    
    return workflow_results

def main():
    """Main application"""
    
    # Initialize session state
    init_session_state()
    
    st.title("🤖 Gen AI Code Converter with AI Test Generation")
    st.write("**4-Phase AI Workflow**: Analysis → Conversion → Validation → AI Test Generation using Amazon Nova Premier")
    
    # Highlight the 4 phases
    st.info("""
    🚀 **4 Phases Involved:**
    - **Phase 1**: AI analyzes code complexity, patterns, and conversion challenges
    - **Phase 2**: AI converts code with context-aware intelligence  
    - **Phase 3**: AI code review and validation
    - **Phase 4**: AI generates comprehensive, executable test cases with persistence
    """)
    
    # Initialize AWS clients
    s3_client, bedrock_runtime = get_aws_clients()
    
    # Initialize Enhanced Gen AI orchestrator
    orchestrator = GenAIWorkflowOrchestrator(bedrock_runtime)
    
    # Get S3 buckets
    try:
        buckets = [b['Name'] for b in s3_client.list_buckets().get('Buckets', [])]
    except Exception as e:
        st.error(f"Error fetching S3 buckets: {e}")
        buckets = []
    
    # Basic configuration
    st.subheader("📁 S3 Configuration")
    col1, col2 = st.columns(2)
    with col1:
        source_bucket = st.selectbox("Source S3 bucket:", buckets, key="source_bucket")
    with col2:
        target_bucket = st.selectbox("Target S3 bucket:", buckets, key="target_bucket")
    
    # Simple prefix filter
    prefix = st.text_input("Folder prefix (optional) (e.g., 'etl/' to scan only the etl folder) :", 
                          help="e.g., 'etl/' to scan only the etl folder", 
                          key="prefix")
    
    # Conversion template selection
    st.subheader("🎯 AI Conversion Template")
    template_options = ["Custom"] + list(CONVERSION_TEMPLATES.keys())
    selected_template = st.selectbox(
        "Choose AI conversion template:", 
        template_options,
        help="Select a pre-configured AI template for optimal conversion",
        key="template"
    )
    
    # Show template description
    if selected_template != "Custom":
        template_info = get_template_info(selected_template)
        if template_info:
            st.info(f"🤖 **AI Template**: {template_info['description']}")
    
    # Language selection
    col1, col2 = st.columns(2)
    with col1:
        if selected_template != "Custom":
            template_info = get_template_info(selected_template)
            if template_info:
                default_source = template_info['source_language']
                source_idx = list(BULK_CONVERSION_LANGUAGES.keys()).index(default_source) if default_source in BULK_CONVERSION_LANGUAGES else 0
            else:
                source_idx = 0
        else:
            source_idx = 0
        source_language = st.selectbox("Source language:", list(BULK_CONVERSION_LANGUAGES.keys()), 
                                     index=source_idx, key="source_lang")
    
    with col2:
        if selected_template != "Custom":
            template_info = get_template_info(selected_template)
            if template_info:
                default_target = template_info['target_language']
                target_idx = list(BULK_CONVERSION_LANGUAGES.keys()).index(default_target) if default_target in BULK_CONVERSION_LANGUAGES else 1
            else:
                target_idx = 1
        else:
            target_idx = 1 if len(BULK_CONVERSION_LANGUAGES) > 1 else 0
        target_language = st.selectbox("Target language:", list(BULK_CONVERSION_LANGUAGES.keys()), 
                                     index=target_idx, key="target_lang")
    
    # Custom patterns (only show if Custom template selected)
    custom_source_pattern = ""
    custom_target_pattern = ""
    
    if selected_template == "Custom":
        st.subheader("🛠️ Custom AI Conversion Patterns")
        st.write("Define custom patterns for AI to understand and convert:")
        col1, col2 = st.columns(2)
        with col1:
            custom_source_pattern = st.text_area(
                "Source patterns to find:",
                placeholder="e.g., spark.sql(), DataFrame.collect()",
                help="Patterns or code snippets for AI to look for in source files",
                key="source_pattern"
            )
        with col2:
            custom_target_pattern = st.text_area(
                "Target patterns to convert to:",
                placeholder="e.g., session.sql(), df.collect()",
                help="What AI should convert the source patterns to",
                key="target_pattern"
            )
    
    # File discovery section
    st.subheader("🔍 File Discovery")
    
    # Scan button
    if st.button("🔍 Scan S3 Bucket for Files", type="primary", key="scan_button"):
        file_extension = BULK_CONVERSION_LANGUAGES[source_language]
        
        with st.spinner(f"Scanning {source_bucket} for {file_extension} files..."):
            matching_files = scan_s3_bucket_for_files(s3_client, source_bucket, prefix, file_extension)
        
        if matching_files:
            # Store in session state
            st.session_state.matching_files = matching_files
            
            st.success(f"Found **{len(matching_files)}** {source_language} files")
            
            # Show sample files
            st.write("**📋 Sample Files Found:**")
            for file_info in matching_files[:5]:  # Show first 5 files
                st.write(f"📄 `{file_info['key']}` ({file_info['size_kb']} KB)")
            if len(matching_files) > 5:
                st.write(f"... and {len(matching_files) - 5} more files")
        else:
            st.warning(f"No {source_language} files found in bucket {source_bucket}")
            if prefix:
                st.info(f"Searched in folder: {prefix}")
            st.session_state.matching_files = []
    
    # Conversion section (only show if files are found)
    if st.session_state.matching_files:
        st.subheader("🚀 Gen AI Workflow with Test Generation")
        
        # Processing options (simplified)
        use_parallel = False  # Disable parallel processing to avoid UI issues
        max_workers = 1
        
        # Cost estimation
        total_files = len(st.session_state.matching_files)
        estimated_tokens_per_file = 3000  # Conservative estimate for 4-phase workflow
        total_estimated_tokens = total_files * estimated_tokens_per_file
        estimated_cost = (total_estimated_tokens / 1000) * 0.003
        
        st.info(f"""
        📊 **Estimated AI Usage:**
        - Files to process: {total_files}
        - Estimated tokens: {total_estimated_tokens:,} (across all 4 phases)
        - Estimated cost: ${estimated_cost:.3f}
        - Processing: Sequential (AI analysis + conversion + validation + test generation)
        - Test files: Generated locally and uploaded to S3
        """)
        
        st.success("✨ AI will generate comprehensive, executable test cases for each converted file!")
        
        # Conversion button
        if st.button("🤖 Start Gen AI Workflow", type="primary", key="convert_button") and not st.session_state.conversion_in_progress:
            st.session_state.conversion_in_progress = True
            
            # Start Gen AI workflow
            workflow_results = process_files_with_enhanced_genai_workflow(
                orchestrator,
                st.session_state.matching_files, 
                source_bucket, target_bucket, 
                source_language, target_language,
                selected_template, custom_source_pattern, custom_target_pattern,
                use_parallel, max_workers
            )
            
            st.session_state.conversion_in_progress = False
    
    # Show previous results if available
    if st.session_state.workflow_results:
        st.subheader("📊 Enhanced GenAI Workflow Summary - Previous Results")
        st.write("**Complete 4-Phase AI Workflow Results**: Analysis → Conversion → Validation → Test Generation")
        
        # Show what's included in the summary
        total_results = len(st.session_state.workflow_results)
        successful_results = len([r for r in st.session_state.workflow_results if r['success']])
        test_files_generated = len([r for r in st.session_state.workflow_results if r.get('test_file_key') or r.get('test_file_path')])
        
        st.info(f"""
        **This summary includes results from {total_results} processed files:**
        - ✅ {successful_results} files successfully converted with AI
        - 🧪 {test_files_generated} AI-generated test files created
        - 📊 Complete metrics for all 4 AI processing phases
        - 💰 Token usage and cost analysis
        - 🎯 AI confidence scores and quality assessments
        """)
        
        display_workflow_summary(st.session_state.workflow_results)
        
        # Show test file management section
        test_files = [r for r in st.session_state.workflow_results if r.get('test_file_key') or r.get('test_file_path')]
        if test_files:
            st.subheader("🧪 Test File Management")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**📁 Local Test Files:**")
                local_files = [r for r in test_files if r.get('test_file_path')]
                if local_files:
                    for result in local_files[:5]:  # Show first 5
                        st.write(f"• `{result['test_file_path']}`")
                    if len(local_files) > 5:
                        st.write(f"... and {len(local_files) - 5} more files")
                    st.info("💡 Test files are saved in the `generated_tests/` directory")
                else:
                    st.write("No local test files generated")
            
            with col2:
                st.write("**☁️ S3 Test Files:**")
                s3_files = [r for r in test_files if r.get('test_file_key')]
                if s3_files:
                    for result in s3_files[:5]:  # Show first 5
                        st.write(f"• `{result['test_file_key']}`")
                    if len(s3_files) > 5:
                        st.write(f"... and {len(s3_files) - 5} more files")
                    st.info(f"💡 Test files uploaded to `{target_bucket}` bucket")
                else:
                    st.write("No S3 test files uploaded")
            
            # Test execution reminder
            st.warning("""
            ⚠️ **Important**: AI-generated test cases require manual execution and validation:
            1. Download test files from S3 or check the `generated_tests/` directory
            2. Install required testing frameworks (pytest, junit, jest, etc.)
            3. Review and modify test cases as needed for your environment
            4. Execute tests to validate conversion accuracy
            5. Use test results to verify production readiness
            """)

if __name__ == "__main__":
    main()

