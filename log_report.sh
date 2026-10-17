#!/usr/bin/bash
#
# Apache log report - summarises the web server's access and error logs
# Log format reference (why $1 = IP, $7 = page, $9 = status code):
#   https://httpd.apache.org/docs/2.4/logs.html
# awk field printing: https://www.gnu.org/software/gawk/manual/html_node/Print-Examples.html
# grep: https://www.gnu.org/software/grep/manual/grep.html
# sort, uniq, wc, head, tail: https://www.gnu.org/software/coreutils/manual/coreutils.html
#
ACCESS_LOG=/var/log/httpd/access_log
ERROR_LOG=/var/log/httpd/error_log

echo "===== Apache Log Report ====="

# the httpd log folder belongs to root, so sudo is needed even to check it exists
if ! sudo test -f $ACCESS_LOG
then
    echo "No access log found - has the web server started?"
    exit 1
fi

echo "Total requests: $(sudo cat $ACCESS_LOG | wc -l)"
echo "Unique visitor IPs: $(sudo awk '{print $1}' $ACCESS_LOG | sort -u | wc -l)"
echo ""
echo "Requests by status code:"
sudo awk '{print $9}' $ACCESS_LOG | sort | uniq -c | sort -rn
echo ""
echo "Not found (404) requests: $(sudo grep -c '" 404 ' $ACCESS_LOG)"
echo ""
echo "Most requested pages:"
sudo awk '{print $7}' $ACCESS_LOG | sort | uniq -c | sort -rn | head -5
echo ""
echo "Last 5 error log entries:"
ERRORS=$(sudo grep -i "error" $ERROR_LOG | tail -5)
echo "${ERRORS:-(no errors found)}"
