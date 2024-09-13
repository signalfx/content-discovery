echo "Benchmark RabbitMQ"
systemd-run -p ****** bash -c "/home/centos/perf-test_linux_x86_64 com.rabbitmq.perf.PerfTest -h amqp://admin:splunk@localhost:5672/vh1 --queue-pattern 'perf-test-%d'   --queue-pattern-from 1 --queue-pattern-to 10   --producers 10 --consumers 10 -f persistenet -z 180"
