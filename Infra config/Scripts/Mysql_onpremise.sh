mysql -h 127.0.0.1 -u root -***** -e "CREATE DATABASE IF NOT EXISTS customer_db";
mysql -h 127.0.0.1 -u root -***** -e "CREATE DATABASE IF NOT EXISTS sales_db";
sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=127.0.0.1 --mysql-port=3306 --mysql-user=root --mysql-password=Splunk@123 --mysql-db=customer_db --db-driver=mysql --tables=10 --table-size=10  prepare
sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=127.0.0.1 --mysql-port=3306 --mysql-user=root --mysql-password=Splunk@123 --mysql-db=customer_db --db-driver=mysql --tables=10 --table-size=10 --delete_inserts=10 --index_updates=10 --non_index_updates=10 --report-interval=10 --threads=128 --time=60 run
sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=127.0.0.1 --mysql-port=3306 --mysql-user=root --mysql-password=Splunk@123 --mysql-db=sales_db --db-driver=mysql --tables=10 --table-size=10  prepare
sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=127.0.0.1 --mysql-port=3306 --mysql-user=root --mysql-password=Splunk@123 --mysql-db=sales_db --db-driver=mysql --tables=10 --table-size=10 --delete_inserts=10 --index_updates=10 --non_index_updates=10 --report-interval=10 --threads=128 --time=60 run
mysql -h 127.0.0.1 -u root -***** -e "DROP DATABASE customer_db";
mysql -h 127.0.0.1 -u root -***** -e "DROP DATABASE sales_db";
