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

    # one line per request, so counting lines counts requests
echo "Total requests: $(sudo cat $ACCESS_LOG | wc -l)"
    # field 1 = visitor IP, sort -u keeps one of each, then count them
echo "Unique visitor IPs: $(sudo awk '{print $1}' $ACCESS_LOG | sort -u | wc -l)"
echo ""
    # field 9 = status code. sort | uniq -c | sort -rn = count each one, biggest first
echo "Requests by status code:"
sudo awk '{print $9}' $ACCESS_LOG | sort | uniq -c | sort -rn
echo ""
    # grep -c counts matching lines - '" 404 ' matches the status code right after the request
echo "Not found (404) requests: $(sudo grep -c '" 404 ' $ACCESS_LOG)"
echo ""
    # field 7 = page requested, top 5 by count
echo "Most requested pages:"
sudo awk '{print $7}' $ACCESS_LOG | sort | uniq -c | sort -rn | head -5
echo ""
    # grep -i = case-insensitive, tail -5 = the 5 most recent
    # ${ERRORS:-...} prints the message instead if nothing was found
echo "Last 5 error log entries:"
ERRORS=$(sudo grep -i "error" $ERROR_LOG | tail -5)
echo "${ERRORS:-(no errors found)}"
