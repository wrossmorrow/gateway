FROM envoyproxy/envoy:v1.21-latest

# SOC2 will require an upgrade
RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y curl python3 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* /var/lib/apt/lists/*

ADD https://raw.githubusercontent.com/envoyproxy/envoy/v1.20.0/restarter/hot-restarter.py /etc/hot-restarter.py
COPY ./envoy/start-envoy.sh /etc/start-envoy.sh
COPY ./envoy/envoy-gateway.yaml /etc/envoy-gateway.yaml
RUN mkdir generated
ADD generated /generated
RUN chmod go+r /etc/envoy-gateway.yaml /etc/hot-restarter.py

CMD ["python3", "/etc/hot-restarter.py", "/etc/start-envoy.sh"]