# OG CODE PUT INTO random_code_4_ca.py, THIS VERSION IS USING FUCTIONS (makes more sense in my mind esp coding with python?)
    # !!! check above in class to make sure this is okay !!!

import sys
import uuid # imported for usage in bucket naming
import boto3
from botocore.exceptions import ClientError, WaiterError
import json
import requests
import subprocess # runs terminal commands 
import time # used to wait between ssh retries
from datetime import datetime # using to timestamp ami name

# SETTINGS / VARIABLES --------------
ami_id = 'ami-0fef201115eefe936'
instance_type = 't2.nano'
availability_zone = 'us-east-1b'
key_name = 'awskey'
key_file = 'awskey.pem'
    # preestablished security group with http + ssh allowed , refactor to create new security group & check if there's one existing already
security_group = 'sg-0fc7eca295775e4d3'
instance_name = f'mroche-inst-{uuid.uuid4().hex[:3]}'

    # startup script - patches os, installs & starts apache, builds index page with instance metadata
    # includes small css styling for the table just to add a personal touch to it 
user_data = """#!/bin/bash
            yum update -y
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd
            
            TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
            META="http://169.254.169.254/latest/meta-data"
            INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/instance-id)
            PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/public-ipv4)
            AMI_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/ami-id)
            AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/placement/availability-zone)

            cat <<EOF > /var/www/html/index.html
            <html>
            <head>
            <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            table { border-collapse: collapse; }
            th, td { border: 1px solid #999; padding: 8px 16px; text-align: left; }
            th { background-color: #eee; }
            </style>
            </head>
            <body>
            <h1>Madison's DevOps Web Server</h1>
            <h3><i>Built automatically with Python and Boto3 for DevOps Assignment 1!</i></h3>
            <table>
            <tr><th>Instance ID</th><td>$INSTANCE_ID</td></tr>
            <tr><th>Public IP</th><td>$PUBLIC_IP</td></tr>
            <tr><th>AMI ID</th><td>$AMI_ID</td></tr>
            <tr><th>Availability Zone</th><td>$AZ</td></tr>
            </table>
            </body></html>
            EOF
            """
            
    # index and error pages to be created and uploaded to the s3 bucket
index_html = """<html>
            <head><title>Madison's S3 Website</title></head>
            <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>Madison's S3 Website</h1>
            <img src="logo.jpg" alt="Logo">
            </body>
            </html>"""
            
error_html = """<html>
            <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>Page Not Found</h1>
            </body>
            </html>"""

ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')


# EC2 -------------------------------
def launch_instance():
    try:
        new_instances = ec2.create_instances(
            ImageId = ami_id,
            MinCount = 1,
            MaxCount = 1,
            InstanceType = instance_type,
            Placement = {'AvailabilityZone': availability_zone},
            KeyName = key_name,
            # takes the user data from above
            UserData = user_data,
            # security group id inputted for existing secutiry group, maybe change to making a security group & checking if one already exists
            SecurityGroupIds = [security_group],
            TagSpecifications = [
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': instance_name
                        }
                    ]
                }
            ])
    except ClientError as error:
        print('Could Not Launch Instance: ', error)
        return None
    
    # printing instance name and id to the console
    instance = new_instances[0]
    print('Instance Launched: ', instance.id)
    print('Instance Name: ', instance_name)
    return instance

    # waits for instance to load before printing the public ip of said instance to the terminal
def wait_for_instance(instance):
    print('Waiting for instance to start running..!')
    try:
        instance.wait_until_running()
    except WaiterError as error:
        print('Instance Did Not Reach Running State: ', error)
        return False

    instance.reload()
    print('Instance Running! Public IP: ', instance.public_ip_address)
    return True


# BUCKETS ---------------------------
def setup_bucket():
    bucket_name = f'{uuid.uuid4().hex[:6]}-mroche'
    try:
        s3.create_bucket(Bucket=bucket_name)
        print('Bucket Created: ', bucket_name)
    except ClientError as error:
        print('Could Not Create Bucket: ', error)
        return None
    website_configuration = {
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    try:
        bucket_website = s3.BucketWebsite(bucket_name)
        bucket_website.put(WebsiteConfiguration=website_configuration)
        print('Status Website Hosting Enabled!')
    except ClientError as error:
        print('Could Not Set Up Website Hosting: ', error)
        return None
        
        # s3 blocks public access by default - remove the block, then add a public-read policy below
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": f"arn:aws:s3:::{bucket_name}/*"
        }]
    }

    try:
        s3.meta.client.delete_public_access_block(Bucket=bucket_name)
        s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))
        print('Bucket Made Public!')
    except ClientError as error:
        print('Could Not Make Bucket Public: ', error)
        return None
        
    return bucket_name
    
# MONITORING --------------------------------
def run_monitoring(instance):
    ip = instance.public_ip_address
    ssh_options = f'-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i {key_file}'

    # ssh usually isn't ready the moment the instance says 'running', so retry the copy
    copied = False
    for attempt in range(1, 11):
        if run_command(f'scp {ssh_options} monitoring.sh ec2-user@{ip}:.'):
            copied = True
            break
        print(f'SSH Not Ready Yet (Attempt {attempt}/10) - Retrying In 10 Seconds...')
        time.sleep(10)

    if not copied:
        print('Could Not Copy monitoring.sh To Instance')
        return False
        
    if not run_command(f"ssh {ssh_options} ec2-user@{ip} 'chmod 700 monitoring.sh'"):
        print('Could Not Set Permissions On monitoring.sh')
        return False

    if not run_command(f"ssh {ssh_options} ec2-user@{ip} './monitoring.sh'"):
        print('Monitoring Script Failed')
        return False

    return True
    
def wait_for_web_server(instance, timeout=600):
    # user data takes a few minutes (yum update, apache install, building the page)
    # so keep checking the page until our own heading shows up
    url = f'http://{instance.public_ip_address}'
    print('Waiting For Web Server To Finish Setting Up...')
    start = time.time()

    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200 and "Madison's DevOps Web Server" in response.text:
                print('Web Server Is Up!')
                return True
        except requests.exceptions.RequestException:
            pass # server not answering yet - just try again

        print('Not Ready Yet - Checking Again In 15 Seconds...')
        time.sleep(15)

    print('Web Server Did Not Start Within', timeout, 'Seconds')
    return False
        
        
# AMI ---------------------------------------
def create_ami(instance):
    # name format from the spec: initials-date-microseconds e.g. MR-2026-10-16-157852
    ami_name = f"MR-{datetime.now().strftime('%Y-%m-%d-%f')}"
    try:
        image = instance.create_image(Name=ami_name)
    except ClientError as error:
        print('Could Not Create AMI: ', error)
        return None

    print('AMI Creation Started: ', image.id)
    print('AMI Name: ', ami_name)
    return image
    
    
# HELPERS -----------------------------------
def download_logo():
    try:
        response = requests.get('http://devops.setudemo.net/logo.jpg', timeout=10)
        response.raise_for_status()  # treats 404 etc. as an error
    except requests.exceptions.RequestException as error:
        print('Could Not Download Logo: ', error)
        return False

    with open('logo.jpg', 'wb') as file:  # 'wb' = write binary, since it's an image
        file.write(response.content)
    print('Logo Downloaded!')
    return True
    
def upload_file(bucket_name, file_name, content_type):
    # content type tells the browser to display the file instead of downloading it
    try:
        with open(file_name, 'rb') as file:
            s3.Object(bucket_name, file_name).put(Body = file, ContentType = content_type)
        print('Uploaded: ', file_name)
        return True
    except (ClientError, OSError) as error:
        print('Could Not Upload', file_name, ': ', error)
        return False
 
def upload_website(bucket_name):
    # write the html pages to local files so they can be uploaded
    with open('index.html', 'w') as file:
        file.write(index_html)
    with open('error.html', 'w') as file:
        file.write(error_html)
 
    return (upload_file(bucket_name, 'logo.jpg', 'image/jpeg')
            and upload_file(bucket_name, 'index.html', 'text/html')
            and upload_file(bucket_name, 'error.html', 'text/html'))
            
def print_to_file(bucket_name, instance):
    try:
        with open('mroche-websites.txt', 'w') as file:
            file.write(f'S3 Website: http://{bucket_name}.s3-website-us-east-1.amazonaws.com\n')
            file.write(f'EC2 Website: http://{instance.public_ip_address}\n')
    except OSError as error:
        print('Could Not Write To File: ', error)
        return False
    print('URLs Written To File - mroche-websites.txt!')
    return True

def run_command(cmd):
    # prints the command and its return code, as the tips doc recommends for debugging
    print('Running: ', cmd)
    result = subprocess.run(cmd, shell=True)
    print('Return Code: ', result.returncode)
    return result.returncode == 0

# MAIN ------------------------------
def main():
    instance = launch_instance()
    if instance is None:
        sys.exit(1) # nothing can work without the instance , quit if no instance

    bucket_name = setup_bucket()
    if bucket_name is None:
        print('S3 Setup Failed - Continuing With EC2 Setup')
    elif not download_logo() or not upload_website(bucket_name):
        print('S3 Website Upload Failed - Continuing With EC2 Setup')
    else:
        print('S3 Website: ', f'http://{bucket_name}.s3-website-us-east-1.amazonaws.com')

    if not wait_for_instance(instance):
        print('Remember to Terminate Instance: ', instance.id, 'In The Console!')
        sys.exit(1)
        print_to_file(bucket_name, instance)

    if not wait_for_web_server(instance):
        print('Web Server Not Ready - Skipping Monitoring And AMI')
        sys.exit(1)

    if not run_monitoring(instance):
        print('Monitoring Failed - Continuing...')
    else:
        print('Monitoring Worked!')

    if create_ami(instance) is None:
        print('AMI Creation Failed')
        sys.exit(1)

    print('All Done!')

    # more steps cont. here in further steps

if __name__ == '__main__':
    main()
