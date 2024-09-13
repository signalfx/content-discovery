# bits-utility

## Getting started with apache

Apache is available within CentOS’s default software repositories, which means you can install it with the yum package manager.

As the non-root sudo user configured in the prerequisites, update the local Apache httpd package index to reflect the latest upstream changes:

 sudo yum update httpd

Once the packages are updated, install the Apache package:

* sudo yum install httpd

After confirming the installation, yum will install Apache and all required dependencies.

If you completed the Additional Recommended Steps for New CentOS 7 Servers guide mentioned in the prerequisites section, you will have installed firewalld on your server and you’ll need to open up port 80 to allow Apache to serve requests over HTTP. If you haven’t already done so, you can do this by enabling firewalld’s http service with the following command:

* sudo firewall-cmd --permanent --add-service=http

If you plan to configure Apache to serve content over HTTPS, you will also want to open up port 443 by enabling the https service:

* sudo firewall-cmd --permanent --add-service=https

Next, reload the firewall to put these new rules into effect:

* sudo firewall-cmd --reload

After the firewall reloads, you are ready to start the service and check the web server.

Checking your Web Server

Apache does not automatically start on CentOS once the installation completes. You will need to start the Apache process manually:

* sudo systemctl start httpd

Verify that the service is running with the following command:

* sudo systemctl status httpd

You will see an active status when the service is running:

Output:
```
Redirecting to /bin/systemctl status httpd.service
● httpd.service - The Apache HTTP Server
   Loaded: loaded (/usr/lib/systemd/system/httpd.service; enabled; vendor preset: disabled)
   Active: active (running) since Wed 2019-02-20 01:29:08 UTC; 5s ago
     Docs: man:httpd(8)
           man:apachectl(8)
 Main PID: 1290 (httpd)
   Status: "Processing requests..."
   CGroup: /system.slice/httpd.service
           ├─1290 /usr/sbin/httpd -DFOREGROUND
           ├─1291 /usr/sbin/httpd -DFOREGROUND
           ├─1292 /usr/sbin/httpd -DFOREGROUND
           ├─1293 /usr/sbin/httpd -DFOREGROUND
           ├─1294 /usr/sbin/httpd -DFOREGROUND
           └─1295 /usr/sbin/httpd -DFOREGROUND
...
```
As you can see from this output, the service appears to have started successfully. However, the best way to test this is to request a page from Apache.

You can access the default Apache landing page to confirm that the software is running properly through your IP address. 

enter it into your browser’s address bar:

```

> http://your_server_ip


You’ll see the default CentOS 7 Apache web page

```

After Installation Checks

# Add This in "/etc/httpd/conf/httpd.conf" file

```

<IfModule mod_status.c>
ExtendedStatus On
</IfModule>
<Location /server-status>
    SetHandler server-status
    Allow from all
</Location>

```


# Add This in "/etc/httpd/conf.modules.d/"

```

<IfModule mpm_worker_module>
ServerLimit 250
StartServers 10
MinSpareThreads 75
MaxSpareThreads 250
ThreadLimit 64
ThreadsPerChild 32
MaxRequestWorkers 8000
MaxConnectionsPerChild 10000
</IfModule>

```
         

# Load Genrator For apache:

Create SH file and add below contant 

``` 

 for i in {1..10};do ab -k -n 100000 -c 1000 http://localhost/;done

* ab -n 10000 -c 100 -H "Accept-Encoding: gzip, deflate" -rk http://localhost/
* echo "Wait for 5sec"
* sleep 5
* ab -n 10000 -c 100 -p /home/centos/data.json -T application/json -rk http://localhost/

```

