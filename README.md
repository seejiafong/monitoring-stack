
Loki is configured with seaweedFS. Create the following buckets:
To run up seaweedFS:
cd seaweedFS
docker run -d \
  -p 9333:9333 \
  -p 9332:8080 \
  -p 8333:8333 \
  -v $(pwd)/data:/data \
  -v $(pwd)/s3.conf:/etc/seaweedfs/s3.conf \
  chrislusf/seaweedfs \
  server -dir=/data -volume.max=5 -s3 -s3.config=/etc/seaweedfs/s3.conf
  
Load the bruno seaweedfs .bru
PUT http://localhost:8333/loki-ruler
PUT http://localhost:8333/loki-chunks
PUT http://localhost:8333/loki-admin
PUT http://localhost:8333/tempo-traces


#helm install <release-name> <chart-folder> -f <values-file>
helm install prom ./prometheus -f prometheus-values.yaml
helm install tempo ./tempo-distributed -f tempo-values.yaml
helm install loki ./loki -f loki-values-seaweed.yaml
helm install otel-collector ./opentelemetry-collector -f otel-collector-values.yaml
helm install grafana ./grafana -f grafana-values.yaml



