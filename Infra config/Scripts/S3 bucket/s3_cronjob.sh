aws s3 cp /home/ubuntu/activemq-all-5.16.3.jar s3://bits-test-alb/AWSLogs/906383545488/
sleep 1
aws s3 cp s3://bits-test-alb/VSCode-darwin-universal.zip /home/ubuntu/
sleep 1
aws s3 rm s3://bits-test-alb/AWSLogs/906383545488/activemq-all-5.16.3.jar
sleep 1
rm -rf /home/ubuntu/VSCode-darwin-universal.zip
sleep 1
wget https://bits-test-alb.s3.us-west-1.amazonaws.com/AWSLogs/906383545488/elasticloadbalancing/