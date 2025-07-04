''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
'''

import json
import os
import time
import logging
import random
from typing import Dict, List, Any, Optional
from datetime import datetime
import streamlit as st
from botocore.exceptions import ClientError
import boto3

# Use Nova Premier for all Gen AI operations
MODEL_ID = "us.amazon.nova-premier-v1:0"

class AITestCaseGenerator:
    """AI-powered test case generator using Nova Premier"""
    
    def __init__(self, bedrock_runtime):
        self.bedrock_runtime = bedrock_runtime
        self.model_id = MODEL_ID
        self.s3_client = boto3.client('s3')
    
    def generate_comprehensive_tests_with_ai(self, original_code: str, converted_code: str,
                                           source_language: str, target_language: str,
                                           template_name: str, file_key: str,
                                           target_bucket: str = None) -> Dict[str, Any]:
        """Generate comprehensive AI-powered test cases"""
        
        test_generation_result = {
            'success': False,
            'test_cases': [],
            'test_file_content': '',
            'test_file_key': '',
            'execution_instructions': '',
            'tokens_used': 0,
            'generation_time': 0.0,
            'issues': []
        }
        
        start_time = time.time()
        
        try:
            st.write("🤖 **AI Test Generation**: Analyzing code for comprehensive test scenarios...")
            
            # Generate test cases using AI
            ai_test_cases = self._generate_ai_test_cases(
                original_code, converted_code, source_language, target_language, template_name
            )
            
            if not ai_test_cases:
                test_generation_result['issues'].append("AI test case generation failed")
                return test_generation_result
            
            # Create comprehensive test file
            test_file_content = self._create_test_file(
                ai_test_cases, target_language, template_name, file_key
            )
            
            # Generate execution instructions
            execution_instructions = self._generate_execution_instructions(
                target_language, template_name, ai_test_cases
            )
            
            # Save test file locally and to S3 if bucket provided
            test_file_path = self._save_test_file_locally(
                test_file_content, file_key, target_language
            )
            
            test_file_key = ""
            if target_bucket:
                test_file_key = self._upload_test_file_to_s3(
                    test_file_content, file_key, target_bucket, target_language
                )
            
            # Populate result
            test_generation_result.update({
                'success': True,
                'test_cases': ai_test_cases,
                'test_file_content': test_file_content,
                'test_file_path': test_file_path,
                'test_file_key': test_file_key,
                'execution_instructions': execution_instructions,
                'tokens_used': self._estimate_tokens_used(original_code, converted_code),
                'generation_time': time.time() - start_time
            })
            
            st.success(f"✅ Generated {len(ai_test_cases)} AI-powered test cases")
            
        except Exception as e:
            test_generation_result['issues'].append(f"Test generation error: {str(e)}")
            logging.error(f"AI test generation failed: {e}")
        
        return test_generation_result
    
    def _generate_ai_test_cases(self, original_code: str, converted_code: str,
                               source_language: str, target_language: str,
                               template_name: str) -> List[Dict[str, Any]]:
        """Generate test cases using Nova Premier AI"""
        
        test_prompt = self._build_test_generation_prompt(
            original_code, converted_code, source_language, target_language, template_name
        )
        
        system_prompt = f"""You are an expert test engineer specializing in {target_language} testing. Generate comprehensive, executable test cases for the converted code.

REQUIREMENTS:
1. Create realistic, executable test cases that validate functionality
2. Include unit tests, integration tests, and edge case tests
3. Generate actual test code, not placeholders
4. Cover error handling and boundary conditions
5. Include setup and teardown where needed
6. Use appropriate testing frameworks for {target_language}

Return your response in this exact JSON format:
{{
    "test_cases": [
        {{
            "name": "test_function_name",
            "type": "unit|integration|edge_case|performance",
            "description": "Clear description of what this test validates",
            "test_code": "Complete executable test code",
            "setup_code": "Any setup code needed",
            "teardown_code": "Any cleanup code needed",
            "expected_outcome": "What should happen when test passes",
            "priority": "high|medium|low",
            "dependencies": ["list", "of", "dependencies"],
            "test_data": "Sample data needed for test"
        }}
    ],
    "test_framework": "pytest|unittest|jest|junit",
    "setup_instructions": "Instructions for test environment setup",
    "execution_command": "Command to run the tests"
}}

IMPORTANT: Return ONLY valid JSON with complete, executable test code."""
        
        try:
            response = self._call_bedrock(system_prompt, test_prompt)
            if response:
                cleaned_response = self._clean_json_response(response)
                if cleaned_response:
                    ai_result = json.loads(cleaned_response)
                    return ai_result.get('test_cases', [])
            
            # Fallback to template-based tests if AI fails
            return self._generate_template_based_tests(template_name, target_language)
            
        except Exception as e:
            logging.error(f"AI test generation failed: {e}")
            return self._generate_template_based_tests(template_name, target_language)
    
    def _build_test_generation_prompt(self, original_code: str, converted_code: str,
                                    source_language: str, target_language: str,
                                    template_name: str) -> str:
        """Build comprehensive test generation prompt"""
        
        prompt = f"""Generate comprehensive test cases for this {template_name} code conversion:

ORIGINAL {source_language} CODE:
```{source_language.lower()}
{original_code[:2000]}  # Limit for prompt size
```

CONVERTED {target_language} CODE:
```{target_language.lower()}
{converted_code[:2000]}  # Limit for prompt size
```

CONVERSION CONTEXT: {template_name}

TEST REQUIREMENTS:
1. **Functional Tests**: Verify the converted code produces the same results as original
2. **Integration Tests**: Test interactions with external systems/libraries
3. **Edge Case Tests**: Test boundary conditions, empty inputs, error scenarios
4. **Performance Tests**: Basic performance validation where applicable
5. **Data Validation Tests**: Verify data transformations are correct

SPECIFIC FOCUS AREAS:"""
        
        # Add template-specific test focus areas
        focus_areas = self._get_template_test_focus(template_name)
        prompt += f"\n{focus_areas}"
        
        prompt += f"""

GENERATE TESTS FOR:
- Core functionality validation
- Error handling and edge cases
- Data integrity and transformations
- Performance characteristics
- Integration points
- Security considerations (if applicable)

Make tests realistic and executable in a {target_language} environment."""
        
        return prompt
    
    def _get_template_test_focus(self, template_name: str) -> str:
        """Get template-specific test focus areas"""
        
        focus_areas = {
            "PySpark → Snowpark": """
- Session creation and configuration
- DataFrame operations equivalence
- SQL query execution
- UDF functionality
- Data type conversions
- Performance comparison
- Connection handling""",
            
            "Bash → Python": """
- File system operations
- Command execution equivalence
- Environment variable handling
- Exit codes and error handling
- Cross-platform compatibility
- Subprocess behavior
- Permission handling""",
            
            "Pandas → Polars": """
- DataFrame operations equivalence
- Aggregation functions
- Join operations
- Data type handling
- Memory usage optimization
- Lazy evaluation
- Performance benchmarks""",
            
            "R → Python": """
- Statistical function equivalence
- Data frame operations
- Plotting functionality
- Package imports
- Data type conversions
- Mathematical operations
- Statistical accuracy""",
            
            "PowerShell → Python": """
- Cmdlet equivalence
- Pipeline operations
- Object handling
- Error management
- Cross-platform compatibility
- Administrative functions
- System interactions"""
        }
        
        return focus_areas.get(template_name, "- General functionality validation\n- Error handling\n- Performance characteristics")
    
    def _create_test_file(self, test_cases: List[Dict[str, Any]], target_language: str,
                         template_name: str, file_key: str) -> str:
        """Create comprehensive test file content"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_name = os.path.basename(file_key)
        
        # Language-specific test file templates
        if target_language.lower() == "python":
            return self._create_python_test_file(test_cases, template_name, file_name, timestamp)
        elif target_language.lower() == "java":
            return self._create_java_test_file(test_cases, template_name, file_name, timestamp)
        elif target_language.lower() == "javascript":
            return self._create_javascript_test_file(test_cases, template_name, file_name, timestamp)
        else:
            return self._create_generic_test_file(test_cases, target_language, template_name, file_name, timestamp)
    
    def _create_python_test_file(self, test_cases: List[Dict[str, Any]], 
                                template_name: str, file_name: str, timestamp: str) -> str:
        """Create Python test file with pytest framework"""
        
        test_content = f'''"""
AI-Generated Test Cases for {template_name} Conversion
Original File: {file_name}
Generated: {timestamp}
Framework: pytest

Installation: pip install pytest
Run tests: pytest {file_name.replace(".", "_")}_tests.py -v
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, List

# Add the converted module to path if needed
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TestConvertedCode:
    """Test suite for AI-converted code validation"""
    
    def setup_method(self):
        """Setup for each test method"""
        pass
    
    def teardown_method(self):
        """Cleanup after each test method"""
        pass

'''
        
        # Add individual test cases
        for i, test_case in enumerate(test_cases):
            test_content += self._format_python_test_case(test_case, i)
        
        # Add utility methods
        test_content += '''
    def _compare_results(self, original_result: Any, converted_result: Any, tolerance: float = 1e-6) -> bool:
        """Compare results with tolerance for floating point numbers"""
        if isinstance(original_result, (int, float)) and isinstance(converted_result, (int, float)):
            return abs(original_result - converted_result) < tolerance
        return original_result == converted_result
    
    def _validate_data_structure(self, data: Any, expected_type: type) -> bool:
        """Validate data structure type and basic properties"""
        return isinstance(data, expected_type)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        
        return test_content
    
    def _format_python_test_case(self, test_case: Dict[str, Any], index: int) -> str:
        """Format individual Python test case"""
        
        test_name = test_case.get('name', f'test_case_{index}')
        description = test_case.get('description', 'AI-generated test case')
        test_code = test_case.get('test_code', 'assert True  # Placeholder')
        setup_code = test_case.get('setup_code', '')
        teardown_code = test_case.get('teardown_code', '')
        priority = test_case.get('priority', 'medium')
        test_type = test_case.get('type', 'unit')
        
        formatted_test = f'''
    @pytest.mark.{priority}
    @pytest.mark.{test_type}
    def {test_name}(self):
        """
        {description}
        Type: {test_type}
        Priority: {priority}
        """
'''
        
        if setup_code:
            formatted_test += f'''        # Setup
        {setup_code}
        
'''
        
        formatted_test += f'''        # Test execution
        {test_code}
'''
        
        if teardown_code:
            formatted_test += f'''        
        # Cleanup
        {teardown_code}
'''
        
        return formatted_test
    
    def _create_java_test_file(self, test_cases: List[Dict[str, Any]], 
                              template_name: str, file_name: str, timestamp: str) -> str:
        """Create Java test file with JUnit framework"""
        
        class_name = file_name.replace(".", "_").title() + "Test"
        
        test_content = f'''/**
 * AI-Generated Test Cases for {template_name} Conversion
 * Original File: {file_name}
 * Generated: {timestamp}
 * Framework: JUnit 5
 * 
 * Run with: mvn test
 */

import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.junit.jupiter.MockitoExtension;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class {class_name} {{
    
    @BeforeEach
    void setUp() {{
        // Setup for each test
    }}
    
    @AfterEach
    void tearDown() {{
        // Cleanup after each test
    }}
'''
        
        # Add individual test cases
        for i, test_case in enumerate(test_cases):
            test_content += self._format_java_test_case(test_case, i)
        
        test_content += '''
}'''
        
        return test_content
    
    def _format_java_test_case(self, test_case: Dict[str, Any], index: int) -> str:
        """Format individual Java test case"""
        
        test_name = test_case.get('name', f'testCase{index}')
        description = test_case.get('description', 'AI-generated test case')
        test_code = test_case.get('test_code', 'assertTrue(true); // Placeholder')
        priority = test_case.get('priority', 'medium')
        test_type = test_case.get('type', 'unit')
        
        formatted_test = f'''
    /**
     * {description}
     * Type: {test_type}
     * Priority: {priority}
     */
    @Test
    @DisplayName("{description}")
    void {test_name}() {{
        {test_code}
    }}
'''
        
        return formatted_test
    
    def _create_javascript_test_file(self, test_cases: List[Dict[str, Any]], 
                                   template_name: str, file_name: str, timestamp: str) -> str:
        """Create JavaScript test file with Jest framework"""
        
        test_content = f'''/**
 * AI-Generated Test Cases for {template_name} Conversion
 * Original File: {file_name}
 * Generated: {timestamp}
 * Framework: Jest
 * 
 * Run with: npm test
 */

describe('Converted Code Tests', () => {{
    
    beforeEach(() => {{
        // Setup for each test
    }});
    
    afterEach(() => {{
        // Cleanup after each test
    }});
'''
        
        # Add individual test cases
        for i, test_case in enumerate(test_cases):
            test_content += self._format_javascript_test_case(test_case, i)
        
        test_content += '''
});'''
        
        return test_content
    
    def _format_javascript_test_case(self, test_case: Dict[str, Any], index: int) -> str:
        """Format individual JavaScript test case"""
        
        test_name = test_case.get('name', f'test case {index}')
        description = test_case.get('description', 'AI-generated test case')
        test_code = test_case.get('test_code', 'expect(true).toBe(true); // Placeholder')
        priority = test_case.get('priority', 'medium')
        test_type = test_case.get('type', 'unit')
        
        formatted_test = f'''
    test('{test_name} - {description}', () => {{
        // Type: {test_type}, Priority: {priority}
        {test_code}
    }});
'''
        
        return formatted_test
    
    def _create_generic_test_file(self, test_cases: List[Dict[str, Any]], target_language: str,
                                 template_name: str, file_name: str, timestamp: str) -> str:
        """Create generic test file for other languages"""
        
        test_content = f'''/*
 * AI-Generated Test Cases for {template_name} Conversion
 * Original File: {file_name}
 * Generated: {timestamp}
 * Target Language: {target_language}
 */

'''
        
        for i, test_case in enumerate(test_cases):
            test_content += f'''
// Test Case {i+1}: {test_case.get('name', f'test_{i}')}
// Description: {test_case.get('description', 'AI-generated test')}
// Type: {test_case.get('type', 'unit')}
// Priority: {test_case.get('priority', 'medium')}

{test_case.get('test_code', '// Test code placeholder')}

'''
        
        return test_content
    
    def _generate_execution_instructions(self, target_language: str, template_name: str,
                                       test_cases: List[Dict[str, Any]]) -> str:
        """Generate detailed execution instructions"""
        
        instructions = f"""
# Test Execution Instructions for {template_name} Conversion

## Generated Test Cases: {len(test_cases)}

### Prerequisites:
"""
        
        if target_language.lower() == "python":
            instructions += """
1. Install required packages:
   ```bash
   pip install pytest pytest-mock
   ```

2. Install any specific dependencies for your converted code

### Running Tests:
```bash
# Run all tests
pytest test_file.py -v

# Run specific test types
pytest test_file.py -m unit -v
pytest test_file.py -m integration -v
pytest test_file.py -m high -v

# Generate coverage report
pytest test_file.py --cov=your_module --cov-report=html
```
"""
        elif target_language.lower() == "java":
            instructions += """
1. Ensure JUnit 5 and Mockito are in your classpath
2. Add dependencies to your pom.xml or build.gradle

### Running Tests:
```bash
# Maven
mvn test

# Gradle
./gradlew test

# Run specific test class
mvn test -Dtest=YourTestClass
```
"""
        elif target_language.lower() == "javascript":
            instructions += """
1. Install Jest and dependencies:
   ```bash
   npm install --save-dev jest
   ```

### Running Tests:
```bash
# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- test_file.test.js
```
"""
        
        instructions += f"""

### Test Categories Generated:
"""
        
        # Categorize tests
        test_types = {}
        for test_case in test_cases:
            test_type = test_case.get('type', 'unit')
            if test_type not in test_types:
                test_types[test_type] = []
            test_types[test_type].append(test_case.get('name', 'unnamed'))
        
        for test_type, tests in test_types.items():
            instructions += f"- **{test_type.title()} Tests**: {len(tests)} tests\n"
        
        instructions += """
### Important Notes:
1. Review and modify test cases as needed for your specific environment
2. Update import statements to match your module structure
3. Add any missing test data or mock objects
4. Verify that all dependencies are properly installed
5. Run tests in a clean environment to validate conversion accuracy

### Validation Checklist:
- [ ] All tests pass without modification
- [ ] Test coverage is adequate (>80% recommended)
- [ ] Edge cases are properly handled
- [ ] Performance tests show acceptable results
- [ ] Integration tests work with actual dependencies
"""
        
        return instructions
    
    def _save_test_file_locally(self, test_content: str, file_key: str, target_language: str) -> str:
        """Save test file locally"""
        
        # Create tests directory if it doesn't exist
        test_dir = "generated_tests"
        os.makedirs(test_dir, exist_ok=True)
        
        # Generate test file name
        base_name = os.path.basename(file_key).replace(".", "_")
        
        if target_language.lower() == "python":
            test_file_name = f"{base_name}_test.py"
        elif target_language.lower() == "java":
            test_file_name = f"{base_name}Test.java"
        elif target_language.lower() == "javascript":
            test_file_name = f"{base_name}.test.js"
        else:
            test_file_name = f"{base_name}_test.{target_language.lower()}"
        
        test_file_path = os.path.join(test_dir, test_file_name)
        
        # Write test file
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        return test_file_path
    
    def _upload_test_file_to_s3(self, test_content: str, file_key: str, 
                               target_bucket: str, target_language: str) -> str:
        """Upload test file to S3"""
        
        try:
            # Generate S3 key for test file
            base_name = os.path.basename(file_key).replace(".", "_")
            
            if target_language.lower() == "python":
                test_file_key = f"tests/{base_name}_test.py"
            elif target_language.lower() == "java":
                test_file_key = f"tests/{base_name}Test.java"
            elif target_language.lower() == "javascript":
                test_file_key = f"tests/{base_name}.test.js"
            else:
                test_file_key = f"tests/{base_name}_test.{target_language.lower()}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=target_bucket,
                Key=test_file_key,
                Body=test_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            return test_file_key
            
        except Exception as e:
            logging.error(f"Failed to upload test file to S3: {e}")
            return ""
    
    def _generate_template_based_tests(self, template_name: str, target_language: str) -> List[Dict[str, Any]]:
        """Generate template-based tests as fallback"""
        
        template_tests = {
            "PySpark → Snowpark": [
                {
                    "name": "test_session_creation",
                    "type": "integration",
                    "description": "Test Snowpark session creation and configuration",
                    "test_code": """
        from snowflake.snowpark import Session
        
        # Test session creation
        connection_params = {
            "account": "test_account",
            "user": "test_user", 
            "password": "test_password",
            "database": "test_db",
            "schema": "test_schema"
        }
        
        # Mock session for testing
        with patch('snowflake.snowpark.Session.builder') as mock_builder:
            mock_session = Mock()
            mock_builder.configs.return_value.create.return_value = mock_session
            
            session = Session.builder.configs(connection_params).create()
            assert session is not None
            mock_builder.configs.assert_called_once_with(connection_params)
                    """,
                    "priority": "high",
                    "dependencies": ["snowflake-snowpark-python"]
                },
                {
                    "name": "test_dataframe_operations",
                    "type": "unit",
                    "description": "Test DataFrame operations equivalence",
                    "test_code": """
        import pandas as pd
        from snowflake.snowpark import Session
        from unittest.mock import Mock
        
        # Create test data
        test_data = [{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}]
        
        # Mock Snowpark DataFrame
        mock_session = Mock()
        mock_df = Mock()
        mock_session.create_dataframe.return_value = mock_df
        
        # Test DataFrame creation
        df = mock_session.create_dataframe(test_data)
        assert df is not None
        mock_session.create_dataframe.assert_called_once_with(test_data)
                    """,
                    "priority": "high",
                    "dependencies": ["snowflake-snowpark-python", "pandas"]
                }
            ],
            
            "Bash → Python": [
                {
                    "name": "test_file_operations",
                    "type": "functional",
                    "description": "Test file system operations equivalence",
                    "test_code": """
        import os
        import tempfile
        import shutil
        from pathlib import Path
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            
            # Test file creation
            test_file.write_text("test content")
            assert test_file.exists()
            assert test_file.read_text() == "test content"
            
            # Test file operations
            backup_file = Path(temp_dir) / "test_backup.txt"
            shutil.copy2(test_file, backup_file)
            assert backup_file.exists()
            assert backup_file.read_text() == "test content"
                    """,
                    "priority": "high",
                    "dependencies": ["pathlib"]
                },
                {
                    "name": "test_command_execution",
                    "type": "integration",
                    "description": "Test subprocess command execution",
                    "test_code": """
        import subprocess
        import sys
        
        # Test simple command execution
        result = subprocess.run([sys.executable, "--version"], 
                              capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Python" in result.stdout
        
        # Test command with error handling
        result = subprocess.run(["nonexistent_command"], 
                              capture_output=True, text=True)
        assert result.returncode != 0
                    """,
                    "priority": "medium",
                    "dependencies": ["subprocess"]
                }
            ]
        }
        
        return template_tests.get(template_name, [
            {
                "name": "test_basic_functionality",
                "type": "unit",
                "description": "Basic functionality validation test",
                "test_code": "assert True  # Replace with actual test logic",
                "priority": "high",
                "dependencies": []
            }
        ])
    
    def _estimate_tokens_used(self, original_code: str, converted_code: str) -> int:
        """Estimate tokens used for test generation"""
        total_chars = len(original_code) + len(converted_code)
        return int(total_chars * 0.3)  # Rough estimate
    
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
            
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                return None
        
        return None
    
    def _call_bedrock(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Bedrock Nova Premier with retry logic"""
        
        system_list = [{"text": system_prompt}]
        user_message = {
            "role": "user",
            "content": [{"text": user_prompt}]
        }
        
        request_body = {
            "messages": [user_message],
            "system": system_list,
            "inferenceConfig": {"max_new_tokens": 4000}
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
                    delay = min(60, 5 * (2 ** attempt)) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logging.error(f"Bedrock test generation error: {e}")
                    return None
            except Exception as e:
                logging.error(f"Unexpected test generation error: {e}")
                return None
        
        return None

# Export main class
__all__ = ['AITestCaseGenerator']
