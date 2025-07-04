''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
'''

import os
import re
import json
import logging
import time
import random
import fnmatch
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any

import boto3
import streamlit as st
from botocore.exceptions import ClientError

# Enhanced language extensions for bulk conversion focus
BULK_CONVERSION_LANGUAGES = {
    # Data & Analytics
    "Python": ".py",
    "R": ".r", 
    "SQL": ".sql",
    
    # DevOps & Automation
    "Bash": ".sh",
    "PowerShell": ".ps1",
    
    # Scripting & Utilities
    "JavaScript": ".js",
    "TypeScript": ".ts",
    "Go": ".go",
    "PHP": ".php",
    
    # Situational (for specific use cases)
    "Java": ".java",
    "Scala": ".scala",
    "C#": ".cs"
}

# Conversion templates for common patterns
CONVERSION_TEMPLATES = {
    "PySpark → Snowpark": {
        "description": "Convert PySpark ETL scripts to Snowpark",
        "source_language": "Python",
        "target_language": "Python",
        "file_patterns": ["*spark*.py", "*etl*.py", "*transform*.py"],
        "custom_prompt": """
Convert PySpark code to Snowpark. Key transformations:
- Replace 'from pyspark.sql import SparkSession' with 'from snowflake.snowpark import Session'
- Convert spark.sql() to session.sql()
- Transform DataFrame operations to Snowpark equivalents
- Update UDF registration: spark.udf.register() to session.udf.register()
- Convert collect() to collect() but handle differently
- Replace show() with show()
- Update import statements from pyspark to snowflake.snowpark
Maintain the same logic and structure.
        """,
        "validation_patterns": ["snowflake.snowpark", "Session", "session.sql"]
    },
    
    "Pandas → Polars": {
        "description": "Convert Pandas scripts to Polars for better performance",
        "source_language": "Python", 
        "target_language": "Python",
        "file_patterns": ["*pandas*.py", "*data*.py", "*analysis*.py"],
        "custom_prompt": """
Convert Pandas code to Polars. Key transformations:
- Replace 'import pandas as pd' with 'import polars as pl'
- Convert pd.DataFrame() to pl.DataFrame()
- Transform .groupby() operations to Polars syntax
- Update .agg() methods to Polars equivalents
- Convert .merge() to .join()
- Replace .apply() with .map_elements() or .with_columns()
- Update file I/O: pd.read_csv() to pl.read_csv()
Maintain the same data processing logic.
        """,
        "validation_patterns": ["import polars", "pl.", ".lazy()"]
    },
    
    "Bash → Python": {
        "description": "Convert Bash scripts to Python for better maintainability",
        "source_language": "Bash",
        "target_language": "Python", 
        "file_patterns": ["*.sh", "*deploy*.sh", "*setup*.sh"],
        "custom_prompt": """
Convert Bash script to Python. Key transformations:
- Add proper Python shebang: #!/usr/bin/env python3
- Convert shell commands to subprocess calls
- Replace $VAR with proper Python variables
- Convert if/then/else to Python if statements
- Transform for loops to Python for loops
- Replace echo with print()
- Convert file operations to Python file handling
- Add proper error handling with try/except
- Use argparse for command line arguments
Maintain the same functionality and logic flow.
        """,
        "validation_patterns": ["subprocess", "import", "def "]
    },
    
    "R → Python": {
        "description": "Convert R analytics scripts to Python",
        "source_language": "R",
        "target_language": "Python",
        "file_patterns": ["*.r", "*.R", "*analysis*.r", "*stats*.r"],
        "custom_prompt": """
Convert R code to Python. Key transformations:
- Replace library() calls with import statements
- Convert data.frame to pandas DataFrame
- Transform R's <- assignment to Python's =
- Convert R functions to Python functions with def
- Replace R's c() with Python lists []
- Transform apply() family to pandas methods
- Convert ggplot2 to matplotlib/seaborn
- Replace R's summary() with pandas describe()
- Convert R's which() to pandas boolean indexing
Maintain statistical accuracy and data processing logic.
        """,
        "validation_patterns": ["import pandas", "import numpy", "def "]
    },
    
    "SQL Dialect Conversion": {
        "description": "Convert between SQL dialects (e.g., MySQL to PostgreSQL)",
        "source_language": "SQL",
        "target_language": "SQL",
        "file_patterns": ["*.sql", "*query*.sql", "*procedure*.sql"],
        "custom_prompt": """
Convert SQL from source dialect to target dialect. Key considerations:
- Update data type mappings between dialects
- Convert function names (e.g., IFNULL to COALESCE)
- Transform date/time functions
- Update string functions and syntax
- Convert LIMIT/TOP syntax differences
- Transform stored procedure syntax
- Update variable declaration syntax
- Convert comment styles if needed
Maintain query logic and performance characteristics.
        """,
        "validation_patterns": ["SELECT", "FROM", "WHERE"]
    }
}

class FileAnalyzer:
    """Analyze files before conversion"""
    
    @staticmethod
    def analyze_file_content(content: str, file_key: str, source_language: str) -> Dict[str, Any]:
        """Analyze individual file content"""
        lines = content.splitlines()
        analysis = {
            'file_key': file_key,
            'line_count': len(lines),
            'char_count': len(content),
            'complexity': 'simple',
            'estimated_tokens': len(content.split()) * 1.3,
            'issues': [],
            'patterns_found': []
        }
        
        # Complexity assessment
        if analysis['line_count'] > 200:
            analysis['complexity'] = 'complex'
        elif analysis['line_count'] > 50:
            analysis['complexity'] = 'medium'
            
        # Check for potential issues
        content_lower = content.lower()
        if 'todo' in content_lower or 'fixme' in content_lower:
            analysis['issues'].append("Contains TODO/FIXME comments")
            
        if 'deprecated' in content_lower:
            analysis['issues'].append("Contains deprecated code references")
            
        # Language-specific pattern detection
        if source_language == "Python":
            if 'pyspark' in content_lower:
                analysis['patterns_found'].append('PySpark')
            if 'pandas' in content_lower:
                analysis['patterns_found'].append('Pandas')
                
        elif source_language == "Bash":
            if re.search(r'\$\{.*\}', content):
                analysis['patterns_found'].append('Parameter expansion')
            if 'sudo' in content:
                analysis['patterns_found'].append('Privileged operations')
                
        return analysis
    
    @staticmethod
    def analyze_files_batch(s3_client, bucket: str, files: List[str], source_language: str) -> Dict[str, Any]:
        """Analyze multiple files and provide summary"""
        total_analysis = {
            'total_files': len(files),
            'total_size': 0,
            'total_lines': 0,
            'complexity_distribution': {'simple': 0, 'medium': 0, 'complex': 0},
            'estimated_tokens': 0,
            'estimated_cost': 0,
            'estimated_time_minutes': 0,
            'potential_issues': [],
            'patterns_summary': {},
            'file_details': []
        }
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file_key in enumerate(files):
            try:
                status_text.text(f"Analyzing {file_key}...")
                
                response = s3_client.get_object(Bucket=bucket, Key=file_key)
                content = response['Body'].read().decode('utf-8', errors='ignore')
                
                file_analysis = FileAnalyzer.analyze_file_content(content, file_key, source_language)
                total_analysis['file_details'].append(file_analysis)
                
                # Aggregate metrics
                total_analysis['total_size'] += file_analysis['char_count']
                total_analysis['total_lines'] += file_analysis['line_count']
                total_analysis['complexity_distribution'][file_analysis['complexity']] += 1
                total_analysis['estimated_tokens'] += file_analysis['estimated_tokens']
                
                # Aggregate issues
                for issue in file_analysis['issues']:
                    total_analysis['potential_issues'].append(f"{file_key}: {issue}")
                
                # Aggregate patterns
                for pattern in file_analysis['patterns_found']:
                    total_analysis['patterns_summary'][pattern] = total_analysis['patterns_summary'].get(pattern, 0) + 1
                    
            except Exception as e:
                total_analysis['potential_issues'].append(f"{file_key}: Error reading file - {str(e)}")
                
            progress_bar.progress((i + 1) / len(files))
        
        # Calculate estimates
        total_analysis['estimated_cost'] = (total_analysis['estimated_tokens'] / 1000) * 0.003  # Rough estimate
        total_analysis['estimated_time_minutes'] = len(files) * 0.5  # Rough estimate
        
        status_text.empty()
        progress_bar.empty()
        
        return total_analysis

class PatternMatcher:
    """Handle file pattern matching"""
    
    @staticmethod
    def match_patterns(file_key: str, patterns: List[str]) -> bool:
        """Check if file matches any of the given patterns"""
        if not patterns:
            return True
            
        filename = os.path.basename(file_key)
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern.strip()):
                return True
        return False
    
    @staticmethod
    def get_files_by_patterns(s3_client, bucket: str, prefix: str, patterns: List[str], 
                            min_size: int = 0, max_size: int = float('inf'),
                            modified_after: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get files matching patterns with additional filters"""
        matching_files = []
        continuation_token = None
        
        while True:
            try:
                list_params = {'Bucket': bucket, 'Prefix': prefix}
                if continuation_token:
                    list_params['ContinuationToken'] = continuation_token
                    
                response = s3_client.list_objects_v2(**list_params)
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        file_key = obj['Key']
                        file_size = obj['Size']
                        last_modified = obj['LastModified'].replace(tzinfo=None)
                        
                        # Size filter
                        if file_size < min_size * 1024 or file_size > max_size * 1024:
                            continue
                            
                        # Date filter
                        if modified_after and last_modified < modified_after:
                            continue
                            
                        # Pattern filter
                        if PatternMatcher.match_patterns(file_key, patterns):
                            matching_files.append({
                                'key': file_key,
                                'size': file_size,
                                'last_modified': last_modified,
                                'size_kb': round(file_size / 1024, 2)
                            })
                
                if response.get('NextContinuationToken'):
                    continuation_token = response['NextContinuationToken']
                else:
                    break
                    
            except ClientError as e:
                logging.error(f"Error fetching files from bucket {bucket}: {e}")
                st.error(f"Error fetching files from bucket {bucket}: {e}")
                break
                
        return matching_files

class ConversionBatcher:
    """Create intelligent batches for conversion"""
    
    @staticmethod
    def create_batches(file_details: List[Dict[str, Any]], max_batch_size: int = 10) -> Dict[str, List[str]]:
        """Group files into intelligent batches based on complexity"""
        batches = {
            'simple_files': [],      # < 50 lines, process in parallel
            'medium_files': [],      # 50-200 lines, moderate parallelism  
            'complex_files': [],     # > 200 lines, sequential processing
            'problematic_files': []  # Files with potential issues
        }
        
        for file_detail in file_details:
            file_key = file_detail['file_key']
            
            if file_detail['issues']:
                batches['problematic_files'].append(file_key)
            elif file_detail['complexity'] == 'simple':
                batches['simple_files'].append(file_key)
            elif file_detail['complexity'] == 'medium':
                batches['medium_files'].append(file_key)
            else:
                batches['complex_files'].append(file_key)
        
        return batches

def get_conversion_template_prompt(template_name: str, custom_source_pattern: str = "", 
                                 custom_target_pattern: str = "") -> str:
    """Get the conversion prompt for a template or custom pattern"""
    if template_name in CONVERSION_TEMPLATES:
        template = CONVERSION_TEMPLATES[template_name]
        base_prompt = template['custom_prompt']
        
        # Add custom patterns if provided
        if custom_source_pattern or custom_target_pattern:
            pattern_addition = f"\n\nAdditional custom patterns to consider:\n"
            if custom_source_pattern:
                pattern_addition += f"Source patterns to look for: {custom_source_pattern}\n"
            if custom_target_pattern:
                pattern_addition += f"Target patterns to convert to: {custom_target_pattern}\n"
            base_prompt += pattern_addition
            
        return base_prompt
    else:
        # Custom conversion
        custom_prompt = "Convert the code from source language to target language."
        if custom_source_pattern:
            custom_prompt += f"\n\nLook for these patterns in the source code: {custom_source_pattern}"
        if custom_target_pattern:
            custom_prompt += f"\n\nConvert them to these target patterns: {custom_target_pattern}"
        custom_prompt += "\n\nMaintain the same logic and functionality while following best practices in the target language."
        
        return custom_prompt
