# AI-Enhanced Code Conversion with Automated Test Generation

This project provides an innovative AI-enhanced solution that not only automates code conversion between programming languages but also generates comprehensive test cases to validate the converted code. By leveraging **Amazon Nova Premier** through Amazon Bedrock, this solution delivers a complete **4-phase AI workflow** that transforms code conversion from a risky manual process into a reliable, automated pipeline with built-in quality assurance.

## 4-Phase AI Workflow

The solution implements a comprehensive AI workflow:

**Phase 1: AI-Powered Analysis**
- Intelligent complexity assessment of source code
- Pattern identification and dependency analysis  
- Conversion challenge prediction
- Context understanding for optimal conversion strategy

**Phase 2: AI-Enhanced Conversion**
- Context-aware code translation using analysis insights
- Intelligent chunking based on code complexity
- Structure and logic preservation
- Target language idiom optimization

**Phase 3: AI-Powered Validation**
- Quality assessment of converted code
- Confidence scoring (0-100 scale)
- Issue identification and reporting
- Conversion accuracy verification

**Phase 4: AI Test Generation**
- Comprehensive test case creation
- Framework-specific test generation (pytest, junit, jest, etc.)
- Edge case and integration test coverage
- Dual persistence (local + S3 storage)
- Execution instruction generation

## Business Value

Traditional code conversion approaches face a critical gap: even if code is successfully converted, how do you verify that it works correctly? This solution addresses that challenge by providing:

- **Complete End-to-End Automation** - From initial analysis to final test case generation
- **AI-Powered Quality Assurance** - Built-in validation with confidence scoring
- **Production Readiness** - Generated tests provide validation needed for confident deployment
- **Reduced Time-to-Deployment** - Significantly reduces time from conversion to production

## Features

- **AI-Enhanced Code Conversion** - Context-aware conversion using Amazon Nova Premier
- **Automated Test Generation** - Comprehensive, executable test cases for validation
- **Multi-Language Support** - Python, Java, JavaScript, C++, C#, Go, Scala, PHP, R, Bash, PowerShell, SQL, HTML, CSS, TypeScript, Objective-C
- **Intelligent Processing** - AI analysis drives optimal conversion strategies
- **Dual Test Persistence** - Tests saved locally (`generated_tests/` directory) and uploaded to S3
- **Framework-Specific Tests** - pytest, junit, jest, NUnit, MSTest compatible test generation
- **Real-time Progress Tracking** - Monitor all 4 phases with detailed metrics
- **Confidence Scoring** - AI-powered quality assessment (0-100 scale)
- **Cost Estimation** - Token usage and cost tracking across all phases
- **Error Handling and Logging** - Comprehensive logging with Amazon CloudWatch integration

## Prerequisites

- **AWS Account** with appropriate permissions to access S3 and Amazon Bedrock
- **Python 3.9+** installed
- **AWS CLI** configured with appropriate credentials

### Required AWS Permissions

Your AWS credentials need the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListAllMyBuckets",
                "bedrock:InvokeModel",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:s3:::*",
                "arn:aws:bedrock:*:*:foundation-model/*",
                "arn:aws:logs:*:*:*"
            ]
        }
    ]
}
```

### Required Python Packages

The following packages are included in `requirements.txt`:
- boto3
- streamlit
- watchtower
- botocore

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aws-samples/code-conversion-using-gen-ai.git
   cd code-conversion-using-gen-ai
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials:**
   Ensure your AWS credentials are properly configured with access to S3 and Amazon Bedrock.

## Usage

### Running the AI-Enhanced Application

Start the Streamlit application with the complete 4-phase AI workflow:

```bash
streamlit run app.py
```

### Using the Application

1. **S3 Configuration:**
   - Select source and target S3 buckets
   - Optionally specify a folder prefix to limit scope

2. **AI Conversion Template:**
   - Choose from pre-configured AI templates for optimal conversion
   - Or select "Custom" for specialized conversion patterns

3. **Language Selection:**
   - Select source and target programming languages
   - Templates automatically configure optimal language pairs

4. **File Discovery:**
   - Click "Scan S3 Bucket for Files" to discover source files
   - Review the list of files to be processed

5. **Start AI Workflow:**
   - Click "Start Gen AI Workflow" to begin the 4-phase process
   - Monitor progress through Analysis → Conversion → Validation → Test Generation
   - View real-time metrics including confidence scores and token usage

6. **Review Results:**
   - Examine the comprehensive workflow summary
   - Access generated test files locally and in S3
   - Review AI confidence scores and validation results

## AI Test Generation

The solution generates comprehensive test suites with the following capabilities:

### Test Coverage
- **Unit Tests** - Individual function and method testing
- **Integration Tests** - Component interaction validation
- **Edge Cases** - Boundary condition testing
- **Error Handling** - Exception and error scenario testing

### Framework-Specific Generation
- **Python**: pytest-compatible test files with fixtures and assertions
- **Java**: JUnit test classes with proper annotations
- **JavaScript**: Jest test suites with mocking capabilities
- **C#**: NUnit or MSTest compatible test classes

### Test File Management
- **Local Storage**: Tests saved in `generated_tests/` directory
- **S3 Integration**: Automatic upload to target bucket
- **Organized Structure**: Tests organized by source file and timestamp

## Configuration

You can configure the following settings in `app.py`:

- **Model Configuration**: Amazon Nova Premier model settings
- **Logging**: CloudWatch Log Group and Stream names
- **Processing**: Chunk sizes and parallel processing options
- **Test Generation**: Framework preferences and test types

## Performance

Converting 1,083 lines of Java code to Python with comprehensive test generation:
- **Manual Process**: 40-60 hours (including test case creation)
- **AI-Enhanced Solution**: Under 8 minutes with complete test coverage
- **Processing Rate**: ~2,500 tokens per minute across all 4 phases

## Monitoring and Observability

The solution provides comprehensive monitoring through:

- **Amazon CloudWatch Integration** - Detailed logging across all 4 phases
- **Real-time Metrics** - Progress tracking with token usage and costs
- **AI Confidence Scores** - Quality assessment for each conversion
- **Test Generation Metrics** - Success rates and test case counts
- **Performance Analytics** - Processing times and throughput metrics

## Architecture

The solution runs on AWS compute services (EC2, EKS, ECS) and integrates with:
- **Amazon S3** - Source and target file storage
- **Amazon Bedrock** - AI model access (Nova Premier)
- **Amazon CloudWatch** - Logging and monitoring
- **Streamlit** - User interface and workflow management

## Cleanup

To avoid ongoing charges, delete the following AWS resources:
- S3 buckets (including generated test files)
- IAM roles and policies
- EC2 instances or other compute resources
- CloudWatch log groups

## Next Steps

Looking forward to enhance the solution with future enhancements including:
- **CI/CD Integration** - Automated test execution in pipelines
- **Automated Test Execution** - Immediate feedback on conversion quality
- **Enterprise Integration** - Advanced workflow management and reporting

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

- **Amazon Bedrock** - For providing Amazon Nova Premier AI capabilities
- **Streamlit** - For the excellent Python web application framework
- **AWS Services** - For scalable, reliable cloud infrastructure
