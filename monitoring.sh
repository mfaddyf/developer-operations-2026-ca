#!/usr/bin/bash
#
# Some basic monitoring functionality; Tested on Amazon Linux 2023.
#
TOKEN=`curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
PROCESSES=$(expr $(ps -A | grep -c .) - 1)
HTTPD_PROCESSES=$(ps -A | grep -c httpd)
# asks metadata service for public ip , using token script at top of file
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
# df -h / shows disk space, second takes row 2 col 5 which shows % used
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}')
UPTIME=$(uptime -p)
# holds cpu load averages and prints the first three mins
LOAD=$(awk '{print $1, $2, $3}' /proc/loadavg)
# counts line in apaches access log one line per page request
REQUESTS=$(sudo cat /var/log/httpd/access_log 2>/dev/null | wc -l)

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
echo "Top 5 processes by memory:"
ps aux --sort=-%mem | head -6
