#!/usr/bin/bash
#
# Some basic monitoring functionality; Tested on Amazon Linux 2023.
#
# provided checks ----
    # IMDSv2: get a session token first, then use it to ask the metadata service for values
TOKEN=`curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
    # free -m shows memory in MB - row 2 is "Mem:", used ($3) divided by total ($2) as a percentage
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
    # counts every line of the process list, minus 1 for the header row
PROCESSES=$(expr $(ps -A | grep -c .) - 1)
    # counts how many apache (httpd) processes are running - 0 means the web server is down
HTTPD_PROCESSES=$(ps -A | grep -c httpd)

# added checks ----
    # asks metadata service for public ip , using token script at top of file
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
    # df -h / shows disk space, second takes row 2 col 5 which shows % used
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}')
UPTIME=$(uptime -p)
    # holds cpu load averages and prints the first three mins
LOAD=$(awk '{print $1, $2, $3}' /proc/loadavg)
    # counts line in apaches access log one line per page request
REQUESTS=$(sudo cat /var/log/httpd/access_log 2>/dev/null | wc -l)

    # output -----
echo "Instance ID: $INSTANCE_ID"
echo "Memory utilisation: $MEMORYUSAGE"
echo "No of processes: $PROCESSES"
echo "Public IP: $PUBLIC_IP"
echo "Disk usage (/): $DISK_USAGE"
echo "Uptime: $UPTIME"
echo "Load average (1, 5, 15 min): $LOAD"
echo "Web requests served: $REQUESTS"
if [ $HTTPD_PROCESSES -ge 1 ]
then
    echo "Web server is running"
else
    echo "Web server is NOT running"
fi
    # lists every process, biggest memory users first, keeping the header + top 5
echo "Top 5 processes by memory:"
ps aux --sort=-%mem | head -6
