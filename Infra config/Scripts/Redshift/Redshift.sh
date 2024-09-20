export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*****
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c "DROP TABLE sales; CREATE TABLE sales (id INT,date DATE,product VARCHAR(50),price NUMERIC(10, 2),quantity INT);"
sleep 3
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*****
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " INSERT INTO sales (id, date, product, price, quantity)
VALUES
    (1, '2023-06-01', 'Product A', 10.99, 5),
    (2, '2023-06-02', 'Product B', 20.50, 3),
    (3, '2023-06-03', 'Product C', 15.75, 2);"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=****
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " SELECT * FROM sales;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " UPDATE sales
SET price = price * 1.1
WHERE product = 'Product A'; DELETE FROM sales
WHERE quantity < 3; SELECT product, SUM(price * quantity) AS total_sales
FROM sales
GROUP BY product;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " DROP TABLE sales; DROP USER bitsQA;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******8
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " CREATE USER bitsQA
WITH PASSWORD '******';"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " CREATE SCHEMA dev_schema;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " GRANT USAGE ON SCHEMA dev_schema TO bitsQA;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " REVOKE USAGE ON SCHEMA dev_schema FROM bitsQA;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=**********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c "DROP SCHEMA IF EXISTS dev_schema;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c "DROP USER bitsQA;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c "DROP USER bitsDev;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " CREATE USER bitsDev
WITH PASSWORD 'Crest@123';"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " CREATE SCHEMA prod_schema;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=******
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " GRANT USAGE ON SCHEMA prod_schema TO bitsDev;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c " REVOKE USAGE ON SCHEMA prod_schema FROM bitsDev;"
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=*********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439 -c "DROP SCHEMA IF EXISTS prod_schema;"
sleep 10
export ODBCINI=~/.odbc.ini
export AMAZONREDSHIFTODBCINI=/opt/amazon/redshiftodbc/lib/64/amazon.redshiftodbc.ini
export ODBCSYSINI=/opt/amazon/redshiftodbc/Setup
export RSPASSWORD=**********
rsql -h bits-prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d salesdb -p 5439