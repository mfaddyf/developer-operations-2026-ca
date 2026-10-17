# devops1.py - DevOps Assignment 1 - Madison Roche
# launches an EC2 web server and an S3 static website, writes both URLs to a file,
# runs monitoring + a log report on the instance, shows CloudWatch CPU metrics, then creates an AMI

import sys
import json # used to format the bucket policy
import time # used to wait between ssh retries / web server checks
import uuid # imported for usage in bucket naming
import textwrap # used to indent output from the instance so it stands out
import subprocess # runs terminal commands (scp, ssh) from python
from datetime import datetime, timedelta, timezone # used for the AMI name + cloudwatch time range

import boto3
import requests # used to download the logo + check the web server is up
# exception types from the Boto3 error handling guide:
# https://docs.aws.amazon.com/boto3/latest/guide/error-handling.html
from botocore.exceptions import ClientError, WaiterError

# SETTINGS / VARIABLES --------------
ami_id = 'ami-0fef201115eefe936'
instance_type = 't2.nano'
availability_zone = 'us-east-1b'
key_name = 'awskey'
key_file = 'awskey.pem'
    # preestablished security group with http + ssh allowed , refactor to create new security group & check if there's one existing already
security_group = 'sg-0fc7eca295775e4d3'
instance_name = f'mroche-inst-{uuid.uuid4().hex[:3]}'
logo_url = 'http://devops.setudemo.net/logo.jpg'
    # same ssh options used for every scp/ssh command (StrictHostKeyChecking from Assignment 1 Tips, Step 6)
ssh_options = f'-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i {key_file}'

    # startup script - patches os, installs & starts apache, builds index page with instance metadata
    # includes small css styling for the table just to add a personal touch to it
    # (normal string, NOT an f-string, so python leaves the $ and {} alone)
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

    # page for the S3 website - shows the logo uploaded to the bucket
index_html = """<html>
<head><title>Madison's S3 Website</title></head>
<body style="font-family: Arial, sans-serif; margin: 40px;">
<h1>Madison's S3 Website</h1>
<img src="logo.jpg" alt="Logo">
</body>
</html>"""

    # page S3 shows if someone requests a file that doesn't exist
error_html = """<html>
<body style="font-family: Arial, sans-serif; margin: 40px;">
<h1>Page Not Found</h1>
</body>
</html>"""

ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')
cloudwatch = boto3.client('cloudwatch')


# OUTPUT HELPERS --------------------
# every line gets a tag so it's easy to see at a glance what worked and what didn't
def heading(title):
    print(f'\n========== {title} ==========')

def ok(message):
    print(f'  [OK]     {message}')

def info(message):
    print(f'  [..]     {message}')

def error(message):
    print(f'  [ERROR]  {message}')

def show_block(text):
    # indents output that came from the instance (monitoring / log report) with a | down the side
    if text.strip():
        print(textwrap.indent(text.rstrip(), '           | '))


# EC2 -------------------------------
def launch_instance():
    try:
        new_instances = ec2.create_instances(
            ImageId = ami_id,
            MinCount = 1,
            MaxCount = 1,
            InstanceType = instance_type,
            # detailed monitoring = 1-minute metrics instead of 5-minute:
            # https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/manage-detailed-monitoring.html
            Monitoring = {'Enabled': True},
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
    except ClientError as err:
        error(f'Could Not Launch Instance: {err}')
        return None

    instance = new_instances[0]
    ok(f'Instance Launched: {instance.id} ({instance_name})')
    return instance

def wait_for_instance(instance):
    info('Waiting For Instance To Reach Running State...')
    try:
        instance.wait_until_running()
    except WaiterError as err:
        error(f'Instance Did Not Reach Running State: {err}')
        return False

    instance.reload() # refresh so the public ip is filled in
    ok(f'Instance Running - Public IP: {instance.public_ip_address}')
    return True


# BUCKETS ---------------------------
def setup_bucket():
    # bucket name formatted '6randomchars-mroche'
    bucket_name = f'{uuid.uuid4().hex[:6]}-mroche'
    try:
        s3.create_bucket(Bucket=bucket_name)
        ok(f'Bucket Created: {bucket_name}')
    except ClientError as err:
        error(f'Could Not Create Bucket: {err}')
        return None

    website_configuration = {
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    try:
        bucket_website = s3.BucketWebsite(bucket_name)
        bucket_website.put(WebsiteConfiguration=website_configuration)
        ok('Static Website Hosting Enabled')
    except ClientError as err:
        error(f'Could Not Set Up Website Hosting: {err}')
        return None

    # s3 blocks public access by default - remove the block, then add a public-read policy (Assignment 1 Tips, Step 4)
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
        ok('Bucket Made Public')
    except ClientError as err:
        error(f'Could Not Make Bucket Public: {err}')
        return None

    return bucket_name


# HELPERS ---------------------------
# downloads the logo using the requests library: https://requests.readthedocs.io
def download_logo():
    try:
        response = requests.get(logo_url, timeout=10)
        response.raise_for_status() # treats 404 etc. as an error
    except requests.exceptions.RequestException as err:
        error(f'Could Not Download Logo: {err}')
        return False

    with open('logo.jpg', 'wb') as file: # 'wb' = write binary, since it's an image
        file.write(response.content)
    ok('Logo Downloaded')
    return True

def upload_file(bucket_name, file_name, content_type):
    # content type tells the browser to display the file instead of downloading it (Assignment 1 Tips, Step 4)
    try:
        with open(file_name, 'rb') as file:
            s3.Object(bucket_name, file_name).put(Body = file, ContentType = content_type)
        ok(f'Uploaded: {file_name}')
        return True
    except (ClientError, OSError) as err:
        error(f'Could Not Upload {file_name}: {err}')
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
            if bucket_name is not None: # skip the s3 url if the bucket setup failed
                file.write(f'S3 Website: http://{bucket_name}.s3-website-us-east-1.amazonaws.com\n')
            file.write(f'EC2 Website: http://{instance.public_ip_address}\n')
    except OSError as err:
        error(f'Could Not Write To File: {err}')
        return False

    ok('URLs Written To mroche-websites.txt')
    return True


# MONITORING ------------------------
# runs a terminal command from python using subprocess.run() (Assignment 1 Tips, Step 6)
# prints the command + return code to help with debugging. output is captured so ssh's
# warnings only get shown if the command actually fails
def run_command(cmd, show_output=False):
    print(f'  [CMD]    {cmd}')
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f'           Return Code: {result.returncode}')
    if show_output:
        show_block(result.stdout)
    if result.returncode != 0:
        show_block(result.stderr)
    return result.returncode == 0

# copies monitoring.sh to the instance, sets permissions & runs it - scp/ssh commands as per Assignment 1 Tips, Step 6
def run_monitoring(instance):
    ip = instance.public_ip_address

    # ssh usually isn't ready the moment the instance says 'running', so retry the copy
    copied = False
    for attempt in range(1, 11):
        if run_command(f'scp {ssh_options} monitoring.sh ec2-user@{ip}:.'):
            copied = True
            break
        info(f'SSH Not Ready Yet (Attempt {attempt}/10) - Retrying In 10 Seconds...')
        time.sleep(10)

    if not copied:
        error('Could Not Copy monitoring.sh To Instance')
        return False

    if not run_command(f"ssh {ssh_options} ec2-user@{ip} 'chmod 700 monitoring.sh'"):
        error('Could Not Set Permissions On monitoring.sh')
        return False

    if not run_command(f"ssh {ssh_options} ec2-user@{ip} './monitoring.sh'", show_output=True):
        error('Monitoring Script Failed')
        return False

    return True

# copies log_report.sh to the instance and runs it - scp/ssh commands as per Assignment 1 Tips, Step 6
def run_log_report(instance):
    ip = instance.public_ip_address

    # request a page that doesn't exist, so the report has a 404 to show
    try:
        requests.get(f'http://{ip}/this-page-does-not-exist', timeout=5)
    except requests.exceptions.RequestException:
        pass

    # no retry loop needed - monitoring already proved ssh is working
    if not run_command(f'scp {ssh_options} log_report.sh ec2-user@{ip}:.'):
        error('Could Not Copy log_report.sh To Instance')
        return False

    if not run_command(f"ssh {ssh_options} ec2-user@{ip} 'chmod 700 log_report.sh'"):
        error('Could Not Set Permissions On log_report.sh')
        return False

    if not run_command(f"ssh {ssh_options} ec2-user@{ip} './log_report.sh'", show_output=True):
        error('Log Report Failed')
        return False

    return True


# CLOUDWATCH ------------------------
# gets CPU utilisation for the instance from cloudwatch, based on:
# https://docs.aws.amazon.com/boto3/latest/reference/services/cloudwatch/client/get_metric_statistics.html
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
def get_cpu_utilisation(instance):
    # last 30 minutes, 1 minute at a time (cloudwatch works in UTC)
    start_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    # a brand-new instance can take a few minutes to show up in cloudwatch, so keep checking
    datapoints = []
    for attempt in range(1, 9):
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace = 'AWS/EC2',
                MetricName = 'CPUUtilization',
                Dimensions = [{'Name': 'InstanceId', 'Value': instance.id}],
                StartTime = start_time,
                EndTime = datetime.now(timezone.utc),
                Period = 60,
                Statistics = ['Average', 'Maximum'],
            )
        except ClientError as err:
            error(f'Could Not Get CPU Metrics: {err}')
            return False

        datapoints = response['Datapoints']
        if datapoints:
            break
        info(f'No CPU Data Yet (Attempt {attempt}/8) - Checking Again In 30 Seconds...')
        time.sleep(30)

    if not datapoints:
        info('No CPU Data After 4 Minutes - CloudWatch May Still Be Catching Up')
        return True

    # cloudwatch doesn't return points in time order - sort by timestamp using a key function:
    # https://docs.python.org/3/howto/sorting.html
    datapoints = sorted(datapoints, key=lambda point: point['Timestamp'])

    ok('CPU Utilisation (UTC time):')
    lines = [f"{point['Timestamp'].strftime('%H:%M')}   Average: {point['Average']:6.2f}%   Max: {point['Maximum']:6.2f}%"
             for point in datapoints]
    show_block('\n'.join(lines))
    return True


# AMI -------------------------------
def wait_for_web_server(instance, timeout=600):
    # user data takes a few minutes (yum update, apache install, building the page)
    # so keep checking the page until our own heading shows up
    url = f'http://{instance.public_ip_address}'
    start = time.time()

    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200 and "Madison's DevOps Web Server" in response.text:
                ok(f'Web Server Is Up ({int(time.time() - start)} Seconds)')
                return True
        except requests.exceptions.RequestException:
            pass # server not answering yet - just try again

        info(f'Not Ready Yet ({int(time.time() - start)}s Elapsed) - Checking Again In 15 Seconds...')
        time.sleep(15)

    error(f'Web Server Did Not Start Within {timeout} Seconds')
    return False

def create_ami(instance):
    # name format from the spec: initials-date-microseconds e.g. MR-2026-10-16-157852
    ami_name = f"MR-{datetime.now().strftime('%Y-%m-%d-%f')}"
    try:
        image = instance.create_image(Name=ami_name) # instance.create_image() as per Assignment 1 Tips, Step 7
    except ClientError as err:
        error(f'Could Not Create AMI: {err}')
        return None

    ok(f'AMI Creation Started: {image.id} ({ami_name})')
    info('AMI Will Show As "Pending" In The Console For A Few Minutes')
    return f'{image.id} ({ami_name})'


# MAIN ------------------------------
def main():
    heading('Launching EC2 Instance')
    instance = launch_instance()
    if instance is None:
        sys.exit(1) # nothing can work without the instance , quit if no instance

    # set up S3 while the instance boots
    heading('Setting Up S3 Website')
    s3_url = None
    bucket_name = setup_bucket()
    if bucket_name is None:
        error('S3 Setup Failed - Continuing With EC2 Setup')
    elif not download_logo() or not upload_website(bucket_name):
        error('S3 Website Upload Failed - Continuing With EC2 Setup')
    else:
        s3_url = f'http://{bucket_name}.s3-website-us-east-1.amazonaws.com'
        ok(f'S3 Website: {s3_url}')

    heading('Waiting For Instance')
    if not wait_for_instance(instance):
        error(f'Remember To Terminate Instance {instance.id} In The Console!')
        sys.exit(1)
    ec2_url = f'http://{instance.public_ip_address}'

    heading('Writing URLs To File')
    print_to_file(bucket_name, instance)

    heading('Waiting For Web Server')
    if not wait_for_web_server(instance):
        error('Web Server Not Ready - Skipping Monitoring And AMI')
        sys.exit(1)

    heading('Monitoring')
    if run_monitoring(instance):
        ok('Monitoring Complete')
    else:
        error('Monitoring Failed - Continuing...')

    heading('Apache Log Report')
    if run_log_report(instance):
        ok('Log Report Complete')
    else:
        error('Log Report Failed - Continuing...')

    # cpu metrics before the AMI, since creating the image reboots the instance
    heading('CloudWatch CPU Metrics')
    if not get_cpu_utilisation(instance):
        error('CPU Metrics Failed - Continuing...')

    heading('Creating AMI')
    ami = create_ami(instance)
    if ami is None:
        sys.exit(1)

    # everything important in one place at the end
    heading('Summary')
    print(f'  Instance     : {instance.id} ({instance_name})')
    print(f'  EC2 Website  : {ec2_url}')
    print(f'  S3 Website   : {s3_url or "(S3 setup failed)"}')
    print(f'  AMI          : {ami}')
    print(f'  URLs Saved To: mroche-websites.txt')
    print('\nAll Done!')

if __name__ == '__main__':
    main()
