#!/bin/bash
## monit check for open file limit / file descriptor usage
## reads in all monitored procs in /etc/monit/rules/procs.conf
## if process is using more than 50% of open file limit, send alert

echoerr() { printf "%s\n" "$*" >&2; }

ALLPROCS=$(ps aux | grep -v grep)

ERRLOG=""

while IFS= read -r line;
do
    [ -z "${line}" ] && continue

    PROC=$(echo "${line}" | awk -F"matching" '{print $2}' | xargs | tr -d '"')
    [ -z "${PROC}" ] && continue

    PID=$(echo "${ALLPROCS}" | grep -w "$PROC" | awk '{print $2}')
    [ -z "${PID}" ] && continue

    # get max open files for this process
    if [[ -d /proc/$PID ]]
    then
        MAX=$(sudo /bin/cat /proc/$PID/limits | grep "Max open files" | awk '{print $4}')
        CURRENT=$(sudo /bin/ls /proc/$PID/fd/ | wc -l)
        PCT=$(echo "scale=2; ${CURRENT}*100/${MAX}" | bc)  # get % of open file limit per process

        #echo "${PROC} -- max $MAX, curr $CURRENT, pct $PCT"

        # if process has over 50% open file limit, alert
        if awk "BEGIN {exit !($PCT > 50)}"
        then
            ERRLOG="${ERRLOG}\n [$PID] ${PROC},  max openfiles: ${MAX},  current open files: ${CURRENT},  open file limit: ${PCT}%\n"
        fi
    fi

done < /etc/monit/rules/procs.conf


## notify monit that theres FD limit alert
if [ -n "${ERRLOG}" ]
then
    echo -e "${ERRLOG}" 2> /dev/null
else
    echo "ok"
fi