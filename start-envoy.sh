#!/bin/bash
ulimit -n 102400
sysctl fs.inotify.max_user_watches=524288
exec /usr/local/bin/envoy -c /etc/envoy-gateway.yaml \
    --restart-epoch $RESTART_EPOCH \
    --service-cluster front-proxy \
    --log-level ${LOG_LEVEL:info}
