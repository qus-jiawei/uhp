#!/usr/bin/env bash
# coding=utf-8

[ -z "$UHP_HOME" ] && {
    echo "UHP_HOME not set."
    exit 1
}
echo "UHP_HOME=$UHP_HOME"

app=`basename "$0" .sh`
app=${app#*-} # app=worker

pid=$(cat ${UHP_HOME}/pids/${app}/*.pid 2>/dev/null)
[ -n "$pid" ] && kill $pid

ok="false"
for ((i=0;i<10;i++)); do
    pidfile=$(ls ${UHP_HOME}/pids/${app}/*.pid 2>/dev/null)
    [ -z "$pidfile" ] && {
        echo "Stop OK"
        ok="true"
        break
    }
    sleep 1
done

[ "$ok" == "true" ] && exit 0

echo "Stop OK"
exit 1
