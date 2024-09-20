java -jar /root/cron/kinesis/aws-kpl-demo.jar TickerApp2 us-west-1 300
#!/bin/bash
echo "Inserting DATA"
for i in {0..10}
do
aws kinesis get-records --shard-iterator $(aws kinesis get-shard-iterator --shard-id shardId-000000000000 --shard-iterator-type TRIM_HORIZON --stream-name TickerApp --query 'ShardIterator')
done
cat /root/cron/kinesis/kill.sh
#!/bin/bash
sudo kill -9 $(ps aux | grep '/usr/bin/[p]ython2 -s /usr/bin/aws' | awk '{print $2}')
sudo kill -9 $(ps aux | grep '/usr/bin/[p]ython3.6 /root/cron/kinesis/test.py' | awk '{print $2}')