# Code Conversion using Generative AI
The goal of this project is to facilitate the conversion of a customer's application code from one programming language to another. Customers often have extensive codebases with numerous files in their repositories. Manually converting each individual file would be a time-consuming and cumbersome process.

To address this challenge, the sample code provided aims to recursively scan an S3 bucket for the required files (e.g., .py, .java) and then convert them to the desired programming language one by one. This process involves changing the file extension to match the target programming language and then uploading the converted files to a new S3 bucket.

The sample code takes the following inputs:

* Source programming language
* Target programming language
* Source S3 bucket
* Target S3 bucket

By automating this code conversion process, the project seeks to streamline the task and make it more efficient for the customer.


- For developers this repo shows how quickly you can build a frontend with Streamlit and point that to Amazon Bedrock to leverage available large language models such as Anthropic Claude 3 Sonnet for achieving a repo level code conversion.

## Features
- Convert source code files from one programming language to another

- Support for multiple programming languages (Python, Java, JavaScript, C++, C#, Go, Scala, PHP, R, Bash, PowerShell, SQL, HTML, CSS, TypeScript, Objective-C)

- Parallel file conversion and chunking of code files for improved performance

- Logging and error handling

## Prerequisites

- AWS account with appropriate permissions to access S3 and Amazon Bedrock

Following are the packages to be installed before starting the streamlit app:
- Python 3.9 and above
- boto3
- streamlit
- watchtower

# Installation

Clone the repository:

    git clone https://github.com/your-repo/code-converter.git


## Set up the required AWS credentials and configuration.
Refer the IAM policy to create an user based on the provided sample IAM policy

## Usage
Run the Streamlit application using the command below

    streamlit run app.py

1. In the Streamlit UI, select the source and target S3 buckets.

2. Optionally, enter a prefix for the files you want to convert.

3. Select the source and target programming languages.

4. Click the "Convert Files" button to start the conversion process.

5. Monitor the progress and check the logs for any errors or warnings.

## Configuration

You can configure the following settings in the app.py file:

1. log_group_name: The name of the CloudWatch Log Group for logging.

2. log_stream_name: The name of the CloudWatch Log Stream for logging.

3. model_id: The ID of the generative AI model used for code conversion.

4. max_tokens: The maximum number of tokens the model can generate.

5. system: The system prompt for the model.


# License
This project is licensed under the MIT License. See the LICENSE file.

# Cleanup
The source code in this repository doesnt provision any AWS services. Customer might provision IAM Policy, IAM Role, VPC, Security Groups and EC2 instance or any form of compute to run this application. Please make sure you delete any resource that you provision to avoid recurring AWS cost.

# Acknowledgments
- Streamlit for the awesome Python library for building data apps.
- Amazon Bedrock for providing the generative AI model used in this application.