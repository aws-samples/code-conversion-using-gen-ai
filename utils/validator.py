''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
'''

import json
import random
import time
import logging
import re
from typing import Dict, List, Any, Optional
import streamlit as st
from botocore.exceptions import ClientError

from .test_generator import AITestCaseGenerator

# Use Nova Premier for all Gen AI operations
MODEL_ID = "us.amazon.nova-premier-v1:0"

class GenAIEnhancedAnalyzer:
    """Gen AI-powered file analysis for pre-conversion insights"""
    
    def __init__(self, bedrock_runtime):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = MODEL_ID
    
    def analyze_code_with_ai(self, code_content: str, source_language: str, 
                            target_language: str = None, template_name: str = None) -> Dict[str, Any]:
        """Use Gen AI for comprehensive code analysis"""
        
        analysis_prompt = self._build_analysis_prompt(code_content, source_language, target_language, template_name)
        
        system_prompt = """You are an expert code analyst. Analyze the provided code and provide insights in a structured format.

Return your analysis in this exact JSON format (ensure valid JSON):
{
    "complexity_level": "simple",
    "complexity_score": 75,
    "frameworks_detected": ["framework1", "framework2"],
    "patterns_found": ["pattern1", "pattern2"],
    "potential_issues": ["issue1", "issue2"],
    "conversion_challenges": ["challenge1", "challenge2"],
    "estimated_conversion_confidence": 85,
    "code_quality_score": 80,
    "lines_of_code": 150,
    "functions_count": 5,
    "classes_count": 2,
    "dependencies": ["dep1", "dep2"],
    "recommendations": ["rec1", "rec2"]
}

IMPORTANT: Return ONLY valid JSON, no additional text or explanations."""
        
        try:
            response = self._call_bedrock(system_prompt, analysis_prompt)
            if response:
                # Clean and parse JSON response
                cleaned_response = self._clean_json_response(response)
                if cleaned_response:
                    ai_analysis = json.loads(cleaned_response)
                    return self._enhance_analysis_with_metrics(ai_analysis, code_content)
                else:
                    return self._fallback_analysis(code_content, source_language)
            else:
                return self._fallback_analysis(code_content, source_language)
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error in AI analysis: {e}")
            return self._fallback_analysis(code_content, source_language)
        except Exception as e:
            logging.error(f"AI analysis failed: {e}")
            return self._fallback_analysis(code_content, source_language)
    
    def _build_analysis_prompt(self, code_content: str, source_language: str, 
                              target_language: str = None, template_name: str = None) -> str:
        """Build comprehensive analysis prompt"""
        
        prompt = f"""Analyze this {source_language} code for comprehensive insights:

CODE TO ANALYZE:
```{source_language.lower()}
{code_content[:2000]}  # Limit code size for analysis
```

ANALYSIS REQUIREMENTS:
1. Assess code complexity (simple: <50 lines, medium: 50-200 lines, complex: >200 lines)
2. Detect frameworks, libraries, and patterns used
3. Identify potential conversion challenges
4. Evaluate code quality and maintainability
5. Estimate conversion confidence if converting to {target_language or 'another language'}"""

        if template_name:
            prompt += f"""
6. Specific analysis for {template_name} conversion pattern
7. Pattern-specific challenges and recommendations"""

        prompt += """

Focus on:
- Framework dependencies and their complexity
- Code patterns that may be difficult to convert
- Performance implications
- Security considerations
- Best practices adherence"""

        return prompt
    
    def _clean_json_response(self, response: str) -> Optional[str]:
        """Clean and extract JSON from AI response"""
        if not response or not response.strip():
            return None
            
        # Remove markdown formatting
        response = response.replace('```json', '').replace('```', '').strip()
        
        # Find JSON content between braces
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_content = response[start_idx:end_idx]
            
            # Basic JSON validation
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                # Try to fix common JSON issues
                json_content = self._fix_common_json_issues(json_content)
                try:
                    json.loads(json_content)
                    return json_content
                except json.JSONDecodeError:
                    return None
        
        return None
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        # Fix trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix single quotes to double quotes
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        
        # Fix unquoted keys
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        return json_str
    
    def _enhance_analysis_with_metrics(self, ai_analysis: Dict[str, Any], code_content: str) -> Dict[str, Any]:
        """Enhance AI analysis with calculated metrics"""
        
        # Add calculated metrics
        lines = code_content.splitlines()
        ai_analysis['actual_lines_of_code'] = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        ai_analysis['total_lines'] = len(lines)
        ai_analysis['comment_lines'] = len([line for line in lines if line.strip().startswith('#')])
        ai_analysis['blank_lines'] = len([line for line in lines if not line.strip()])
        
        # Estimate tokens for cost calculation
        word_count = len(code_content.split())
        ai_analysis['estimated_tokens'] = word_count * 1.3
        ai_analysis['estimated_cost'] = (ai_analysis['estimated_tokens'] / 1000) * 0.003
        
        return ai_analysis
    
    def _fallback_analysis(self, code_content: str, source_language: str) -> Dict[str, Any]:
        """Fallback analysis if AI fails"""
        lines = code_content.splitlines()
        line_count = len(lines)
        
        return {
            "complexity_level": "complex" if line_count > 200 else "medium" if line_count > 50 else "simple",
            "complexity_score": min(100, line_count / 2),
            "frameworks_detected": [],
            "patterns_found": [],
            "potential_issues": ["AI analysis unavailable - using basic analysis"],
            "conversion_challenges": [],
            "estimated_conversion_confidence": 70,
            "code_quality_score": 70,
            "lines_of_code": line_count,
            "functions_count": code_content.count('def ') if source_language == "Python" else 0,
            "classes_count": code_content.count('class ') if source_language == "Python" else 0,
            "dependencies": [],
            "recommendations": ["Manual review recommended"],
            "actual_lines_of_code": line_count,
            "total_lines": line_count,
            "estimated_tokens": len(code_content.split()) * 1.3,
            "estimated_cost": (len(code_content.split()) * 1.3 / 1000) * 0.003
        }
    
    def _call_bedrock(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Bedrock with retry logic"""
        
        system_list = [{"text": system_prompt}]
        user_message = {
            "role": "user",
            "content": [{"text": user_prompt}]
        }
        
        request_body = {
            "messages": [user_message],
            "system": system_list,
            "inferenceConfig": {"max_new_tokens": 1500}
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.bedrock_runtime.invoke_model(
                    body=json.dumps(request_body),
                    modelId=self.model_id
                )
                result = json.loads(response['body'].read().decode('utf-8'))
                return result["output"]["message"]["content"][0]['text']
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code', '') == 'ThrottlingException':
                    delay = min(30, 2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logging.error(f"Bedrock error: {e}")
                    return None
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                return None
        
        return None

class GenAIEnhancedConverter:
    """Gen AI-powered code conversion with Nova Premier"""
    
    def __init__(self, bedrock_runtime):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = MODEL_ID
    
    def convert_with_ai_context(self, code_content: str, source_language: str, target_language: str,
                               template_name: str, custom_source_pattern: str = "", 
                               custom_target_pattern: str = "", ai_analysis: Dict[str, Any] = None) -> Optional[str]:
        """Enhanced conversion using AI analysis context"""
        
        # Build context-aware conversion prompt
        conversion_prompt = self._build_enhanced_conversion_prompt(
            code_content, source_language, target_language, template_name,
            custom_source_pattern, custom_target_pattern, ai_analysis
        )
        
        system_prompt = f"""You are an expert code conversion specialist. Convert code accurately while preserving functionality, logic, and performance characteristics.

CONVERSION REQUIREMENTS:
1. Maintain exact functional equivalence
2. Follow best practices in the target language
3. Preserve code structure and readability
4. Handle edge cases and error conditions
5. Optimize for performance where possible

OUTPUT FORMAT:
- Provide only the converted code
- No explanations or markdown formatting
- No code block markers
- Clean, production-ready code"""

        try:
            response = self._call_bedrock(system_prompt, conversion_prompt)
            if response:
                return self._clean_converted_code(response)
            return None
        except Exception as e:
            logging.error(f"AI conversion failed: {e}")
            return None
    
    def _build_enhanced_conversion_prompt(self, code_content: str, source_language: str, 
                                        target_language: str, template_name: str,
                                        custom_source_pattern: str, custom_target_pattern: str,
                                        ai_analysis: Dict[str, Any] = None) -> str:
        """Build enhanced conversion prompt with AI analysis context"""
        
        prompt = f"""Convert this {source_language} code to {target_language}.

CONVERSION TEMPLATE: {template_name}

SOURCE CODE:
```{source_language.lower()}
{code_content}
```

CONVERSION CONTEXT:"""

        # Add AI analysis context if available
        if ai_analysis:
            prompt += f"""
- Code Complexity: {ai_analysis.get('complexity_level', 'unknown')}
- Frameworks Detected: {', '.join(ai_analysis.get('frameworks_detected', []))}
- Patterns Found: {', '.join(ai_analysis.get('patterns_found', []))}"""

        # Add template-specific instructions
        template_instructions = self._get_template_instructions(template_name)
        if template_instructions:
            prompt += f"""

TEMPLATE-SPECIFIC INSTRUCTIONS:
{template_instructions}"""

        # Add custom patterns if provided
        if custom_source_pattern or custom_target_pattern:
            prompt += f"""

CUSTOM PATTERNS:
- Source patterns to convert: {custom_source_pattern}
- Target patterns to use: {custom_target_pattern}"""

        prompt += f"""

CONVERSION REQUIREMENTS:
1. Convert to idiomatic {target_language} code
2. Maintain all functionality and logic
3. Handle error cases appropriately
4. Follow {target_language} best practices
5. Optimize for performance and readability"""

        return prompt
    
    def _get_template_instructions(self, template_name: str) -> str:
        """Get template-specific conversion instructions"""
        
        instructions = {
            "PySpark → Snowpark": """
- Replace 'from pyspark.sql import SparkSession' with 'from snowflake.snowpark import Session'
- Convert SparkSession.builder to Session.builder.configs()
- Replace spark.sql() with session.sql()
- Update DataFrame operations to Snowpark equivalents
- Convert UDF registration syntax
- Maintain SQL query logic exactly""",
            
            "Bash → Python": """
- Add proper Python shebang: #!/usr/bin/env python3
- Convert shell commands to subprocess calls or Python equivalents
- Replace $VAR with Python variables
- Convert loops and conditionals to Python syntax
- Add proper error handling with try/except
- Use argparse for command line arguments
- Ensure cross-platform compatibility""",
            
            "Pandas → Polars": """
- Replace 'import pandas as pd' with 'import polars as pl'
- Convert pd.DataFrame() to pl.DataFrame()
- Transform .groupby() to .group_by()
- Update .agg() methods to Polars syntax
- Convert .merge() to .join()
- Use .lazy() for performance optimization
- Replace .apply() with .map_elements() or .with_columns()""",
            
            "R → Python": """
- Replace library() calls with import statements
- Convert data.frame to pandas DataFrame
- Transform <- assignment to =
- Convert R functions to Python functions with def
- Replace c() with Python lists []
- Convert ggplot2 to matplotlib/seaborn
- Transform statistical functions to pandas/numpy equivalents""",
            
            "PowerShell → Python": """
- Convert cmdlets to Python equivalents (Get-ChildItem → os.listdir)
- Transform pipeline operations to method chaining or loops
- Replace PowerShell variables with Python variables
- Add proper imports (os, shutil, subprocess)
- Implement cross-platform compatibility
- Add error handling with try/except"""
        }
        
        return instructions.get(template_name, "")
    
    def _clean_converted_code(self, converted: str) -> str:
        """Clean up converted code"""
        # Remove common markers and formatting
        converted = converted.replace('<target_code>', '').replace('</target_code>', '').strip()
        converted = converted.replace('```python', '').replace('```java', '').replace('```', '').strip()
        
        # Remove explanation text
        lines = converted.split('\n')
        code_lines = []
        skip_explanation = False
        
        for line in lines:
            line_lower = line.lower().strip()
            if (line_lower.startswith('here') or line_lower.startswith('the converted') or 
                line_lower.startswith('this code') or line_lower.startswith('note:')):
                skip_explanation = True
                continue
            if skip_explanation and line.strip() == '':
                continue
            if skip_explanation and (line.startswith('import ') or line.startswith('def ') or 
                                   line.startswith('class ') or line.startswith('#')):
                skip_explanation = False
            
            if not skip_explanation:
                code_lines.append(line)
        
        return '\n'.join(code_lines).strip()
    
    def _call_bedrock(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Bedrock with retry logic"""
        
        system_list = [{"text": system_prompt}]
        user_message = {
            "role": "user",
            "content": [{"text": user_prompt}]
        }
        
        request_body = {
            "messages": [user_message],
            "system": system_list,
            "inferenceConfig": {"max_new_tokens": 3000}
        }
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.bedrock_runtime.invoke_model(
                    body=json.dumps(request_body),
                    modelId=self.model_id
                )
                result = json.loads(response['body'].read().decode('utf-8'))
                return result["output"]["message"]["content"][0]['text']
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code', '') == 'ThrottlingException':
                    delay = min(60, 5 * (2 ** attempt)) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logging.error(f"Bedrock conversion error: {e}")
                    return None
            except Exception as e:
                logging.error(f"Unexpected conversion error: {e}")
                return None
        
        return None

class GenAIEnhancedValidator:
    """Gen AI-powered validation and comprehensive test generation"""
    
    def __init__(self, bedrock_runtime):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = MODEL_ID
        self.test_generator = AITestCaseGenerator(bedrock_runtime)
    
    def validate_with_ai(self, original_code: str, converted_code: str, 
                        source_language: str, target_language: str,
                        template_name: str, ai_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """Comprehensive AI-powered validation"""
        
        validation_prompt = self._build_validation_prompt(
            original_code, converted_code, source_language, target_language, 
            template_name, ai_analysis
        )
        
        system_prompt = """You are an expert code validation specialist. Analyze the code conversion and provide assessment.

Return your validation in this exact JSON format:
{
    "functional_equivalence": 85,
    "code_quality_score": 90,
    "performance_impact": "improved",
    "syntax_valid": true,
    "best_practices_followed": true,
    "potential_issues": ["issue1", "issue2"],
    "conversion_accuracy": 88,
    "maintainability_score": 85,
    "security_considerations": ["consideration1"],
    "performance_notes": ["note1"],
    "recommendations": ["rec1", "rec2"],
    "confidence_score": 87,
    "test_scenarios": ["scenario1", "scenario2"],
    "edge_cases_handled": true,
    "error_handling_improved": true
}

IMPORTANT: Return ONLY valid JSON, no additional text."""
        
        try:
            response = self._call_bedrock(system_prompt, validation_prompt)
            if response:
                cleaned_response = self._clean_json_response(response)
                if cleaned_response:
                    ai_validation = json.loads(cleaned_response)
                    return self._enhance_validation_result(ai_validation, original_code, converted_code)
                else:
                    return self._fallback_validation(original_code, converted_code)
            else:
                return self._fallback_validation(original_code, converted_code)
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error in AI validation: {e}")
            return self._fallback_validation(original_code, converted_code)
        except Exception as e:
            logging.error(f"AI validation failed: {e}")
            return self._fallback_validation(original_code, converted_code)
    
    def generate_tests_with_ai(self, original_code: str, converted_code: str,
                              source_language: str, target_language: str,
                              template_name: str, file_key: str = "",
                              target_bucket: str = None) -> Dict[str, Any]:
        """Generate comprehensive test cases using AI with persistence"""
        
        st.write("🧪 **Enhanced AI Test Generation**: Creating comprehensive test suite...")
        
        # Use the new AI test generator
        test_result = self.test_generator.generate_comprehensive_tests_with_ai(
            original_code, converted_code, source_language, target_language,
            template_name, file_key, target_bucket
        )
        
        if test_result['success']:
            # Display test generation results
            self._display_test_generation_results(test_result)
            
            # Show execution instructions
            if test_result['execution_instructions']:
                with st.expander("📋 Test Execution Instructions", expanded=False):
                    st.markdown(test_result['execution_instructions'])
        
        return test_result
    
    def _display_test_generation_results(self, test_result: Dict[str, Any]):
        """Display comprehensive test generation results"""
        
        test_cases = test_result.get('test_cases', [])
        
        if not test_cases:
            st.warning("⚠️ No test cases were generated")
            return
        
        st.success(f"✅ **Generated {len(test_cases)} AI-powered test cases**")
        
        # Show test file information
        col1, col2 = st.columns(2)
        
        with col1:
            if test_result.get('test_file_path'):
                st.info(f"📁 **Local Test File**: `{test_result['test_file_path']}`")
        
        with col2:
            if test_result.get('test_file_key'):
                st.info(f"☁️ **S3 Test File**: `{test_result['test_file_key']}`")
        
        # Categorize and display test cases
        test_categories = {}
        for test_case in test_cases:
            category = test_case.get('type', 'unit')
            if category not in test_categories:
                test_categories[category] = []
            test_categories[category].append(test_case)
        
        st.write("**🧪 Generated Test Categories:**")
        
        for category, tests in test_categories.items():
            with st.expander(f"{category.title()} Tests ({len(tests)})", expanded=False):
                for test in tests:
                    st.write(f"**{test.get('name', 'unnamed_test')}**")
                    st.write(f"*{test.get('description', 'No description')}*")
                    st.write(f"Priority: {test.get('priority', 'medium')}")
                    
                    if test.get('test_code'):
                        st.code(test['test_code'][:300] + "..." if len(test['test_code']) > 300 else test['test_code'])
                    
                    st.write("---")
        
        # Show test file preview
        if test_result.get('test_file_content'):
            with st.expander("📄 Test File Preview", expanded=False):
                preview_content = test_result['test_file_content'][:1000]
                if len(test_result['test_file_content']) > 1000:
                    preview_content += "\n\n... (truncated, see full file for complete content)"
                st.code(preview_content)
        
        # Performance metrics
        st.write("**📊 Generation Metrics:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Test Cases", len(test_cases))
        with col2:
            st.metric("Generation Time", f"{test_result.get('generation_time', 0):.1f}s")
        with col3:
            st.metric("Estimated Tokens", f"{test_result.get('tokens_used', 0):,}")
    
    def _build_validation_prompt(self, original_code: str, converted_code: str,
                                source_language: str, target_language: str,
                                template_name: str, ai_analysis: Dict[str, Any] = None) -> str:
        """Build comprehensive validation prompt"""
        
        prompt = f"""Validate this {template_name} code conversion:

ORIGINAL {source_language} CODE:
```{source_language.lower()}
{original_code[:1000]}  # Limit for prompt size
```

CONVERTED {target_language} CODE:
```{target_language.lower()}
{converted_code[:1000]}  # Limit for prompt size
```

VALIDATION CRITERIA:
1. Functional Equivalence: Does the converted code perform the same operations?
2. Code Quality: Is the converted code well-structured and maintainable?
3. Performance: Are there performance improvements or degradations?
4. Best Practices: Does it follow {target_language} best practices?
5. Error Handling: Is error handling appropriate and improved?"""

        if ai_analysis:
            prompt += f"""

ORIGINAL CODE ANALYSIS CONTEXT:
- Complexity: {ai_analysis.get('complexity_level', 'unknown')}
- Quality Score: {ai_analysis.get('code_quality_score', 'unknown')}"""

        return prompt
    
    def _clean_json_response(self, response: str) -> Optional[str]:
        """Clean JSON response from AI"""
        if not response or not response.strip():
            return None
            
        # Remove markdown formatting
        response = response.replace('```json', '').replace('```', '').strip()
        
        # Find JSON content
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_content = response[start_idx:end_idx]
            
            # Basic JSON validation
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                # Try to fix common JSON issues
                json_content = self._fix_common_json_issues(json_content)
                try:
                    json.loads(json_content)
                    return json_content
                except json.JSONDecodeError:
                    return None
        
        return None
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        # Fix trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix single quotes to double quotes
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        
        return json_str
    
    def _enhance_validation_result(self, ai_validation: Dict[str, Any], 
                                  original_code: str, converted_code: str) -> Dict[str, Any]:
        """Enhance AI validation with additional metrics"""
        
        # Add basic syntax check
        if not ai_validation.get('syntax_valid'):
            try:
                compile(converted_code, '<string>', 'exec')
                ai_validation['syntax_valid'] = True
            except SyntaxError:
                ai_validation['syntax_valid'] = False
        
        # Add code metrics
        ai_validation['original_lines'] = len(original_code.splitlines())
        ai_validation['converted_lines'] = len(converted_code.splitlines())
        ai_validation['size_change_ratio'] = ai_validation['converted_lines'] / max(ai_validation['original_lines'], 1)
        
        return ai_validation
    
    def _fallback_validation(self, original_code: str, converted_code: str) -> Dict[str, Any]:
        """Fallback validation if AI fails"""
        return {
            "functional_equivalence": 70,
            "code_quality_score": 70,
            "performance_impact": "maintained",
            "syntax_valid": len(converted_code.strip()) > 0,
            "best_practices_followed": True,
            "potential_issues": ["AI validation unavailable"],
            "conversion_accuracy": 70,
            "maintainability_score": 70,
            "security_considerations": [],
            "performance_notes": [],
            "recommendations": ["Manual review recommended"],
            "confidence_score": 70,
            "test_scenarios": [],
            "edge_cases_handled": True,
            "error_handling_improved": True,
            "original_lines": len(original_code.splitlines()),
            "converted_lines": len(converted_code.splitlines())
        }
    
    def _call_bedrock(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Bedrock with retry logic"""
        
        system_list = [{"text": system_prompt}]
        user_message = {
            "role": "user",
            "content": [{"text": user_prompt}]
        }
        
        request_body = {
            "messages": [user_message],
            "system": system_list,
            "inferenceConfig": {"max_new_tokens": 2000}
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.bedrock_runtime.invoke_model(
                    body=json.dumps(request_body),
                    modelId=self.model_id
                )
                result = json.loads(response['body'].read().decode('utf-8'))
                return result["output"]["message"]["content"][0]['text']
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code', '') == 'ThrottlingException':
                    delay = min(30, 2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logging.error(f"Bedrock validation error: {e}")
                    return None
            except Exception as e:
                logging.error(f"Unexpected validation error: {e}")
                return None
        
        return None

# Export main classes
__all__ = [
    'GenAIEnhancedAnalyzer',
    'GenAIEnhancedConverter', 
    'GenAIEnhancedValidator'
]
