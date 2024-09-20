mysql -u admin -***** -hbits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com
mysql -u admin -***** -hbits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com -e "DROP DATABASE bits_c1511ustomer_db";
mysql -u admin -***** -hbits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com -e "CREATE DATABASE bits_c1511ustomer_db";

sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=bits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com --mysql-port=3306 --mysql-user=admin --mysql-password=***** --mysql-db=bits_c1511ustomer_db --db-driver=mysql --tables=10 --table-size=100  prepare


sysbench /usr/share/sysbench/oltp_read_write.lua --mysql-host=bits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com --mysql-port=3306 --mysql-user=admin --mysql-password=***** --mysql-db=bits_c1511ustomer_db --db-driver=mysql --tables=10 --table-size=100 --delete_inserts=10 --index_updates=10 --non_index_updates=10 --report-interval=10 --threads=128 --time=600 run

#mysql -u admin -pCrest##3100 -hbits-mysql-prod.cdw6johvs3ne.us-west-1.rds.amazonaws.com -e "DROP DATABASE c1511ustomer_db";
