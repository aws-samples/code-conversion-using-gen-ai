''' /*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
'''

import json
import time
import logging
from typing import Dict, List, Any, Optional
import streamlit as st

from .validator import (
    GenAIEnhancedAnalyzer,
    GenAIEnhancedConverter, 
    GenAIEnhancedValidator
)

class GenAIWorkflowOrchestrator:
    """Orchestrates the complete Gen AI workflow: Analysis → Conversion → Validation + AI Test Generation"""
    
    def __init__(self, bedrock_runtime):
        self.bedrock_runtime = bedrock_runtime
        self.analyzer = GenAIEnhancedAnalyzer(bedrock_runtime)
        self.converter = GenAIEnhancedConverter(bedrock_runtime)
        self.validator = GenAIEnhancedValidator(bedrock_runtime)
    
    def process_file_complete_workflow(self, file_info: Dict[str, Any], source_bucket: str, 
                                     target_bucket: str, source_language: str, target_language: str,
                                     template_name: str, custom_source_pattern: str = "",
                                     custom_target_pattern: str = "") -> Dict[str, Any]:
        """Complete Gen AI workflow for a single file with enhanced test generation"""
        
        file_key = file_info['key']
        workflow_result = {
            'file_key': file_key,
            'success': False,
            'phase_results': {
                'analysis': None,
                'conversion': None,
                'validation': None,
                'test_generation': None
            },
            'total_tokens_used': 0,
            'total_cost': 0.0,
            'processing_time': 0.0,
            'confidence_score': 0.0,
            'issues': [],
            'target_key': None,
            'test_file_key': None,
            'test_file_path': None
        }
        
        start_time = time.time()
        
        try:
            # Phase 1: AI-Powered Analysis
            st.write(f"🔍 **Phase 1**: AI Analysis - {file_key}")
            analysis_result = self._phase1_ai_analysis(file_info, source_bucket, source_language, 
                                                     target_language, template_name)
            workflow_result['phase_results']['analysis'] = analysis_result
            
            if not analysis_result['success']:
                workflow_result['issues'].append("Phase 1 (Analysis) failed")
                return workflow_result
            
            # Phase 2: AI-Enhanced Conversion
            st.write(f"🔄 **Phase 2**: AI Conversion - {file_key}")
            conversion_result = self._phase2_ai_conversion(
                analysis_result['original_code'], source_language, target_language,
                template_name, custom_source_pattern, custom_target_pattern,
                analysis_result['ai_analysis']
            )
            workflow_result['phase_results']['conversion'] = conversion_result
            
            if not conversion_result['success']:
                workflow_result['issues'].append("Phase 2 (Conversion) failed")
                return workflow_result
            
            # Phase 3: AI-Powered Validation
            st.write(f"✅ **Phase 3**: AI Validation - {file_key}")
            validation_result = self._phase3_ai_validation(
                analysis_result['original_code'], conversion_result['converted_code'],
                source_language, target_language, template_name, analysis_result['ai_analysis']
            )
            workflow_result['phase_results']['validation'] = validation_result
            
            # Phase 4: Enhanced AI Test Generation
            st.write(f"🧪 **Phase 4**: AI Test Generation - {file_key}")
            test_generation_result = self._phase4_ai_test_generation(
                analysis_result['original_code'], conversion_result['converted_code'],
                source_language, target_language, template_name, file_key, target_bucket
            )
            workflow_result['phase_results']['test_generation'] = test_generation_result
            
            # Upload converted file if validation passes
            if validation_result['ai_validation']['confidence_score'] >= 60:
                target_key = self._upload_converted_file(
                    conversion_result['converted_code'], file_key, target_bucket, target_language
                )
                workflow_result['target_key'] = target_key
                workflow_result['success'] = True
                
                # Store test file information
                if test_generation_result.get('success'):
                    workflow_result['test_file_key'] = test_generation_result.get('test_file_key', '')
                    workflow_result['test_file_path'] = test_generation_result.get('test_file_path', '')
            else:
                workflow_result['issues'].append("Validation confidence too low for deployment")
            
            # Calculate totals
            workflow_result['total_tokens_used'] = (
                analysis_result.get('tokens_used', 0) +
                conversion_result.get('tokens_used', 0) +
                validation_result.get('tokens_used', 0) +
                test_generation_result.get('tokens_used', 0)
            )
            workflow_result['total_cost'] = workflow_result['total_tokens_used'] * 0.003 / 1000
            workflow_result['processing_time'] = time.time() - start_time
            workflow_result['confidence_score'] = validation_result['ai_validation']['confidence_score']
            
        except Exception as e:
            workflow_result['issues'].append(f"Workflow error: {str(e)}")
            logging.error(f"Workflow error for {file_key}: {e}")
        
        return workflow_result
    
    def _phase1_ai_analysis(self, file_info: Dict[str, Any], source_bucket: str, 
                           source_language: str, target_language: str, template_name: str) -> Dict[str, Any]:
        """Phase 1: AI-powered code analysis"""
        
        phase_result = {
            'success': False,
            'original_code': '',
            'ai_analysis': {},
            'tokens_used': 0,
            'processing_time': 0.0,
            'issues': []
        }
        
        start_time = time.time()
        
        try:
            # Download file content
            from boto3 import client
            s3_client = client('s3')
            response = s3_client.get_object(Bucket=source_bucket, Key=file_info['key'])
            original_code = response['Body'].read().decode('utf-8', errors='ignore')
            phase_result['original_code'] = original_code
            
            # AI Analysis
            with st.spinner("🤖 AI analyzing code complexity and patterns..."):
                ai_analysis = self.analyzer.analyze_code_with_ai(
                    original_code, source_language, target_language, template_name
                )
                phase_result['ai_analysis'] = ai_analysis
                phase_result['tokens_used'] = ai_analysis.get('estimated_tokens', 0)
                phase_result['success'] = True
            
            # Display analysis results in a simple format (no nested expanders)
            self._display_analysis_results_simple(ai_analysis, file_info['key'])
            
        except Exception as e:
            phase_result['issues'].append(f"Analysis error: {str(e)}")
            logging.error(f"Phase 1 error: {e}")
        
        phase_result['processing_time'] = time.time() - start_time
        return phase_result
    
    def _phase2_ai_conversion(self, original_code: str, source_language: str, target_language: str,
                             template_name: str, custom_source_pattern: str, custom_target_pattern: str,
                             ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: AI-enhanced code conversion"""
        
        phase_result = {
            'success': False,
            'converted_code': '',
            'tokens_used': 0,
            'processing_time': 0.0,
            'chunks_processed': 0,
            'issues': []
        }
        
        start_time = time.time()
        
        try:
            # Chunk code if necessary
            code_chunks = self._chunk_code_intelligently(original_code, ai_analysis)
            phase_result['chunks_processed'] = len(code_chunks)
            
            converted_chunks = []
            total_tokens = 0
            
            with st.spinner(f"🤖 AI converting {len(code_chunks)} code chunks..."):
                for i, chunk in enumerate(code_chunks):
                    st.write(f"Converting chunk {i+1}/{len(code_chunks)}...")
                    
                    converted_chunk = self.converter.convert_with_ai_context(
                        chunk, source_language, target_language, template_name,
                        custom_source_pattern, custom_target_pattern, ai_analysis
                    )
                    
                    if converted_chunk:
                        converted_chunks.append(converted_chunk)
                        total_tokens += len(chunk.split()) * 1.3  # Estimate
                    else:
                        phase_result['issues'].append(f"Chunk {i+1} conversion failed")
                        return phase_result
            
            # Merge chunks
            final_converted = self._merge_converted_chunks(converted_chunks)
            phase_result['converted_code'] = final_converted
            phase_result['tokens_used'] = total_tokens
            phase_result['success'] = True
            
        except Exception as e:
            phase_result['issues'].append(f"Conversion error: {str(e)}")
            logging.error(f"Phase 2 error: {e}")
        
        phase_result['processing_time'] = time.time() - start_time
        return phase_result
    
    def _phase3_ai_validation(self, original_code: str, converted_code: str,
                             source_language: str, target_language: str, template_name: str,
                             ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: AI-powered validation"""
        
        phase_result = {
            'success': False,
            'ai_validation': {},
            'tokens_used': 0,
            'processing_time': 0.0,
            'issues': []
        }
        
        start_time = time.time()
        
        try:
            # AI Validation
            with st.spinner("🤖 AI validating conversion quality..."):
                ai_validation = self.validator.validate_with_ai(
                    original_code, converted_code, source_language, target_language,
                    template_name, ai_analysis
                )
                phase_result['ai_validation'] = ai_validation
            
            # Estimate tokens used
            validation_tokens = (len(original_code) + len(converted_code)) * 0.5
            phase_result['tokens_used'] = validation_tokens
            phase_result['success'] = True
            
            # Display validation results in a simple format
            self._display_validation_results_simple(ai_validation)
            
        except Exception as e:
            phase_result['issues'].append(f"Validation error: {str(e)}")
            logging.error(f"Phase 3 error: {e}")
        
        phase_result['processing_time'] = time.time() - start_time
        return phase_result
    
    def _phase4_ai_test_generation(self, original_code: str, converted_code: str,
                                  source_language: str, target_language: str, 
                                  template_name: str, file_key: str, target_bucket: str) -> Dict[str, Any]:
        """Phase 4: Enhanced AI test generation with persistence"""
        
        phase_result = {
            'success': False,
            'test_cases': [],
            'test_file_key': '',
            'test_file_path': '',
            'tokens_used': 0,
            'processing_time': 0.0,
            'issues': []
        }
        
        start_time = time.time()
        
        try:
            # Generate comprehensive tests using AI
            test_result = self.validator.generate_tests_with_ai(
                original_code, converted_code, source_language, target_language,
                template_name, file_key, target_bucket
            )
            
            if test_result.get('success'):
                phase_result.update({
                    'success': True,
                    'test_cases': test_result.get('test_cases', []),
                    'test_file_key': test_result.get('test_file_key', ''),
                    'test_file_path': test_result.get('test_file_path', ''),
                    'tokens_used': test_result.get('tokens_used', 0),
                    'execution_instructions': test_result.get('execution_instructions', '')
                })
            else:
                phase_result['issues'].extend(test_result.get('issues', []))
            
        except Exception as e:
            phase_result['issues'].append(f"Test generation error: {str(e)}")
            logging.error(f"Phase 4 error: {e}")
        
        phase_result['processing_time'] = time.time() - start_time
        return phase_result
    
    def _chunk_code_intelligently(self, code: str, ai_analysis: Dict[str, Any]) -> List[str]:
        """Intelligently chunk code based on AI analysis"""
        
        complexity = ai_analysis.get('complexity_level', 'medium')
        lines = code.splitlines()
        
        if complexity == 'simple' or len(lines) < 100:
            return [code]  # No chunking needed
        
        # Smart chunking based on functions/classes
        chunks = []
        current_chunk = []
        current_size = 0
        max_chunk_size = 3000 if complexity == 'complex' else 4000
        
        for line in lines:
            current_chunk.append(line)
            current_size += len(line) + 1
            
            # Check for natural break points
            if (current_size > max_chunk_size and 
                (line.strip().startswith('def ') or line.strip().startswith('class ') or 
                 line.strip() == '' or line.strip().startswith('#'))):
                
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _merge_converted_chunks(self, chunks: List[str]) -> str:
        """Merge converted chunks intelligently"""
        if not chunks:
            return ""
        
        if len(chunks) == 1:
            return chunks[0]
        
        # Simple merge with newline separation
        return '\n\n'.join(chunk.strip() for chunk in chunks if chunk.strip())
    
    def _upload_converted_file(self, converted_code: str, original_key: str, 
                              target_bucket: str, target_language: str) -> str:
        """Upload converted file to S3"""
        
        from .file_converter import BULK_CONVERSION_LANGUAGES
        from boto3 import client
        
        target_extension = BULK_CONVERSION_LANGUAGES[target_language]
        target_key = f"{original_key.rsplit('.', 1)[0]}{target_extension}"
        
        s3_client = client('s3')
        s3_client.put_object(
            Bucket=target_bucket,
            Key=target_key,
            Body=converted_code.encode('utf-8')
        )
        
        return target_key
    
    def _display_analysis_results_simple(self, ai_analysis: Dict[str, Any], file_key: str):
        """Display AI analysis results in simple format (no nested expanders)"""
        
        st.write(f"**🔍 AI Analysis Results - {file_key}**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Complexity**: {ai_analysis.get('complexity_level', 'unknown').title()}")
            st.write(f"**Quality Score**: {ai_analysis.get('code_quality_score', 0)}/100")
        
        with col2:
            st.write(f"**Lines of Code**: {ai_analysis.get('lines_of_code', 0)}")
            st.write(f"**Functions**: {ai_analysis.get('functions_count', 0)}")
        
        with col3:
            st.write(f"**Est. Confidence**: {ai_analysis.get('estimated_conversion_confidence', 0)}%")
            st.write(f"**Est. Tokens**: {ai_analysis.get('estimated_tokens', 0):,.0f}")
        
        # Frameworks and patterns
        frameworks = ai_analysis.get('frameworks_detected', [])
        if frameworks:
            st.write(f"**Frameworks Detected**: {', '.join(frameworks)}")
        
        patterns = ai_analysis.get('patterns_found', [])
        if patterns:
            st.write(f"**Patterns Found**: {', '.join(patterns)}")
        
        # Issues and recommendations
        issues = ai_analysis.get('potential_issues', [])
        if issues:
            st.write("**Potential Issues**:")
            for issue in issues[:3]:  # Limit to 3 issues
                st.warning(f"⚠️ {issue}")
        
        recommendations = ai_analysis.get('recommendations', [])
        if recommendations:
            st.write("**AI Recommendations**:")
            for rec in recommendations[:2]:  # Limit to 2 recommendations
                st.info(f"💡 {rec}")
    
    def _display_validation_results_simple(self, ai_validation: Dict[str, Any]):
        """Display AI code review results in simple format"""
        
        confidence = ai_validation.get('confidence_score', 0)
        
        # Color-code based on confidence
        if confidence >= 80:
            status_color = "🟢"
            status_text = "Looks Excellent"
        elif confidence >= 60:
            status_color = "🟡" 
            status_text = "Looks Good"
        else:
            status_color = "🔴"
            status_text = "Needs Review"
        
        st.write(f"**AI Code Review**: {status_color} {status_text} ({confidence}% AI confidence)")
        st.info("ℹ️ **Note**: This is AI-based code analysis. Actual testing required for production validation.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**AI Assessment Metrics**:")
            st.write(f"• AI Thinks Functional Equivalence: {ai_validation.get('functional_equivalence', 0)}%")
            st.write(f"• AI Assessed Code Quality: {ai_validation.get('code_quality_score', 0)}%")
            st.write(f"• AI Pattern Matching: {ai_validation.get('conversion_accuracy', 0)}%")
        
        with col2:
            st.write("**AI Code Analysis**:")
            st.write(f"• Syntax Check: {'✅' if ai_validation.get('syntax_valid') else '❌'}")
            st.write(f"• Pattern Recognition: {'✅' if ai_validation.get('best_practices_followed') else '❌'}")
            st.write(f"• AI Performance Opinion: {ai_validation.get('performance_impact', 'unknown').title()}")
        
        # Issues and recommendations
        issues = ai_validation.get('potential_issues', [])
        if issues:
            st.write("**AI-Identified Potential Issues**:")
            for issue in issues[:2]:  # Limit to 2 issues
                st.warning(f"⚠️ {issue}")

def display_workflow_summary(workflow_results: List[Dict[str, Any]]):
    """Display comprehensive workflow summary with test generation metrics"""
    
    st.subheader("🤖 Complete GenAI Workflow Results & Performance Metrics")
    st.write("**Summary of 4-Phase AI Processing**: Analysis → Code Conversion → AI Validation → Test Generation")
    
    # Add workflow explanation
    st.info("""
    **What this summary contains:**
    - **Phase 1 Results**: AI code analysis and complexity assessment
    - **Phase 2 Results**: AI-powered code conversion with context awareness  
    - **Phase 3 Results**: AI validation and quality scoring
    - **Phase 4 Results**: AI-generated test cases with execution instructions
    - **Overall Metrics**: Success rates, token usage, costs, and confidence scores
    """)
    
    # Overall metrics
    total_files = len(workflow_results)
    successful_files = len([r for r in workflow_results if r['success']])
    total_tokens = sum(r['total_tokens_used'] for r in workflow_results)
    total_cost = sum(r['total_cost'] for r in workflow_results)
    avg_confidence = sum(r['confidence_score'] for r in workflow_results) / total_files if total_files > 0 else 0
    
    # Test generation metrics
    files_with_tests = len([r for r in workflow_results if r.get('test_file_key') or r.get('test_file_path')])
    total_test_cases = sum(len(r['phase_results'].get('test_generation', {}).get('test_cases', [])) for r in workflow_results)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Files Processed", total_files)
    with col2:
        success_rate = (successful_files / total_files) * 100 if total_files > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%", f"{successful_files}/{total_files}")
    with col3:
        st.metric("Total Tokens", f"{total_tokens:,}")
    with col4:
        st.metric("Total Cost", f"${total_cost:.3f}")
    
    # Test generation summary
    st.subheader("🧪 AI Test Generation Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Files with Tests", files_with_tests)
    with col2:
        st.metric("Total Test Cases", total_test_cases)
    with col3:
        test_success_rate = (files_with_tests / total_files) * 100 if total_files > 0 else 0
        st.metric("Test Gen Success", f"{test_success_rate:.1f}%")
    
    # Phase-wise performance
    st.subheader("📊 Phase-wise Performance")
    
    phase_stats = {
        'analysis': {'success': 0, 'total': 0},
        'conversion': {'success': 0, 'total': 0}, 
        'validation': {'success': 0, 'total': 0},
        'test_generation': {'success': 0, 'total': 0}
    }
    
    for result in workflow_results:
        for phase in ['analysis', 'conversion', 'validation', 'test_generation']:
            phase_result = result['phase_results'].get(phase)
            if phase_result:
                phase_stats[phase]['total'] += 1
                if phase_result.get('success', False):
                    phase_stats[phase]['success'] += 1
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        analysis_rate = (phase_stats['analysis']['success'] / max(phase_stats['analysis']['total'], 1)) * 100
        st.metric("Analysis Success", f"{analysis_rate:.1f}%", "Phase 1")
    
    with col2:
        conversion_rate = (phase_stats['conversion']['success'] / max(phase_stats['conversion']['total'], 1)) * 100
        st.metric("Conversion Success", f"{conversion_rate:.1f}%", "Phase 2")
    
    with col3:
        validation_rate = (phase_stats['validation']['success'] / max(phase_stats['validation']['total'], 1)) * 100
        st.metric("Validation Success", f"{validation_rate:.1f}%", "Phase 3")
    
    with col4:
        test_gen_rate = (phase_stats['test_generation']['success'] / max(phase_stats['test_generation']['total'], 1)) * 100
        st.metric("Test Gen Success", f"{test_gen_rate:.1f}%", "Phase 4")
    
    # Test files generated
    if files_with_tests > 0:
        st.subheader("📁 Generated Test Files")
        
        test_files_info = []
        for result in workflow_results:
            if result.get('test_file_key') or result.get('test_file_path'):
                test_info = {
                    'file': result['file_key'],
                    's3_key': result.get('test_file_key', 'N/A'),
                    'local_path': result.get('test_file_path', 'N/A'),
                    'test_count': len(result['phase_results'].get('test_generation', {}).get('test_cases', []))
                }
                test_files_info.append(test_info)
        
        # Display test files in a table format
        for test_info in test_files_info[:5]:  # Show first 5
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"📄 {test_info['file']}")
            with col2:
                if test_info['s3_key'] != 'N/A':
                    st.write(f"☁️ {test_info['s3_key']}")
                if test_info['local_path'] != 'N/A':
                    st.write(f"📁 {test_info['local_path']}")
            with col3:
                st.write(f"🧪 {test_info['test_count']} tests")
        
        if len(test_files_info) > 5:
            st.write(f"... and {len(test_files_info) - 5} more test files")
    
    # Confidence distribution
    st.subheader("📈 AI Confidence Distribution")
    
    high_conf = len([r for r in workflow_results if r['confidence_score'] >= 80])
    med_conf = len([r for r in workflow_results if 60 <= r['confidence_score'] < 80])
    low_conf = len([r for r in workflow_results if r['confidence_score'] < 60])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("High Confidence", high_conf, "≥ 80%")
    with col2:
        st.metric("Medium Confidence", med_conf, "60-79%")
    with col3:
        st.metric("Low Confidence", low_conf, "< 60%")
    
    # Overall assessment
    st.subheader("🎯 Overall AI Assessment")
    
    if success_rate >= 90 and avg_confidence >= 80 and test_success_rate >= 80:
        st.success("🎉 **AI Assessment: Excellent!** High success rate, AI confidence, and comprehensive test coverage.")
        st.info("💡 **Next Step**: Execute generated tests in your environment for production validation.")
    elif success_rate >= 75 and avg_confidence >= 70 and test_success_rate >= 60:
        st.info("✅ **AI Assessment: Good!** Solid AI analysis with good test coverage.")
        st.info("💡 **Next Step**: Review flagged files and execute tests before deployment.")
    elif success_rate >= 60:
        st.warning("⚠️ **AI Assessment: Moderate.** Review failed conversions and low-confidence files.")
        st.info("💡 **Next Step**: Manual review and comprehensive testing required.")
    else:
        st.error("❌ **AI Assessment: Poor.** Significant issues found in AI analysis.")
        st.info("💡 **Next Step**: Consider adjusting conversion approach and extensive manual review.")
    
    # Detailed data breakdown
    st.subheader("📋 Workflow Data Summary - What's Included")
    
    with st.expander("🔍 View Detailed Data Breakdown", expanded=False):
        st.write("**Each workflow result contains the following data:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**📊 Core Metrics:**")
            st.write("• File processing success/failure status")
            st.write("• Total tokens consumed across all 4 phases")
            st.write("• Estimated cost based on token usage")
            st.write("• Processing time per file")
            st.write("• AI confidence scores (0-100%)")
            st.write("• Target file S3 keys (converted files)")
            
            st.write("**🔍 Phase 1 - AI Analysis Data:**")
            st.write("• Code complexity assessment (simple/medium/complex)")
            st.write("• Lines of code count")
            st.write("• Functions and classes detected")
            st.write("• Frameworks and libraries identified")
            st.write("• Code quality scores")
            st.write("• Potential conversion issues flagged")
            st.write("• AI recommendations for conversion")
        
        with col2:
            st.write("**🔄 Phase 2 - AI Conversion Data:**")
            st.write("• Original source code")
            st.write("• AI-converted target code")
            st.write("• Number of code chunks processed")
            st.write("• Conversion patterns applied")
            st.write("• Template-specific transformations")
            
            st.write("**✅ Phase 3 - AI Validation Data:**")
            st.write("• Functional equivalence assessment")
            st.write("• Code quality comparison scores")
            st.write("• Syntax validation results")
            st.write("• Best practices compliance check")
            st.write("• Performance impact analysis")
            st.write("• AI-identified potential issues")
            
            st.write("**🧪 Phase 4 - Test Generation Data:**")
            st.write("• AI-generated test cases (unit/integration)")
            st.write("• Test file S3 keys (uploaded tests)")
            st.write("• Local test file paths")
            st.write("• Test execution instructions")
            st.write("• Framework-specific test templates")
            st.write("• Coverage recommendations")
        
        st.write("**💾 File Outputs Generated:**")
        st.write("• **Converted Code Files**: Uploaded to target S3 bucket")
        st.write("• **Test Files**: Saved locally in `generated_tests/` directory")
        st.write("• **Test Files**: Also uploaded to S3 for team access")
        st.write("• **Execution Scripts**: Instructions for running generated tests")
    
    # Test execution reminder
    if total_test_cases > 0:
        st.info(f"""
        🧪 **Test Execution Reminder**: 
        - {total_test_cases} AI-generated test cases are ready for execution
        - Check the `generated_tests/` directory for local test files
        - Review S3 bucket for uploaded test files
        - Execute tests in your target environment before production deployment
        """)

# Export main classes
__all__ = [
    'GenAIWorkflowOrchestrator',
    'display_workflow_summary'
]
