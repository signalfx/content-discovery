# Prerequisites

- A system running CentOS 7
- A user account with sudo privileges
- A terminal window (Menu > Applications > Utilities > Terminal)
- The Yum package manager (included by default)
- Guide To Installing MySQL on CentOS 7

```
Step 1: Download Repository Packages
```
Open a browser window, and go to the following address:

https://dev.mysql.com/downloads/repo/yum/
---

This page lists MySQL setup packages in the Yum repository.

Find the Red Hat Enterprise Linux version that you want to download. (At the time of writing, the website offers Linux 8, Linux 7 and Linux 6.)

You can click the Download button, which takes you to a registration page. You can sign up if you’d like or select the No thanks, just start my download link.

Download MySQL with wget Command

Alternately, you can open a terminal and use the wget command to save the file. On the web page that lists release versions, you’ll see a gray subtext that shows something like “(mysql80-community-release-el7-1.noarch.rpm)”. That’s the setup package of a specific package.

Copy the name of the desired setup package, then open a terminal window and enter the following command:

sudo wget https://dev.mysql.com/get/mysql80-community-release-el7-3.noarch.rpm
---

The system should reach out and download the files. Make sure you check the website and copy the exact release ID – use that in your terminal command.

Download MySQL repository packages.

Leave the browser window open for the next step.

```
Step 2: Add the Software Repositories
```

The files we just downloaded provide access to the MySQL software repositories. Before adding them, use the md5sum command to authenticate the software:

sudo md5sum mysql80-community-release-el7-3.noarch.rpm
---

The system should respond with a long string of letters and numbers.

Switch back to the MySQL web page and look just below the Download link to find a gray string of numbers labeled MD5.

Compare the MD5 value on the web page to the MD5 value you generated in the terminal window. If they match, proceed to the next step.

Verify the md5sum string with the one on MySQL's website.
If they don’t match, it’s possible that your download was corrupted in transit. Or, it’s possible that the download has been compromised. Repeat Steps 1 and 2 and overwrite the downloaded file. If the MD5 values still don’t match, stop the procedure.

To update the software repositories, use the command:

sudo rpm -ivh mysql80-community-release-el7-3.noarch.rpm
---

Make sure you’ve entered the release version from step 1. This will add 2 new Yum repositories that we can get MySQL from.

```
Step 3: Install MySQL
```

Install MySQL on CentOS by entering the following:

sudo yum install mysql-server
---

Installing MySQL 7 from the terminal console.
The system will ask for confirmation, press Y to confirm.

It should also request that you accept a GPG (Gnu Privacy Guard) key. This is another security confirmation because we just added two new software sources. Press Y again, and the system should download and install the software.

Verify the MySQL GPG key.
```
Note: MySQL includes several security plugins to authenticate connections to the server, password verification and securing storage for sensitive data. All of these are available in the free version.
```

Using MySQL Managing MySQL Service You’ll need to start the MySQL service by entering:

sudo systemctl start mysqld
---

To check the status of MySQL use the command:

sudo systemctl status mysqld
---

The system will display several lines of information about the MySQL service. In the Active line, it should display active: (running). You may also see a line below that shows a timestamp of when the service was started.

Check whether MySQL service is running. By default, the MySQL service is set to launch at startup.

To disable it, you can use the disable command:

sudo systemctl disable mysqld
---

To stop the MySQL service, use the stop command:

sudo systemctl stop mysqld
---

Find Temporary Password The MySQL installation routine sets up a default temporary password.

Use the grep command to find the password:

sudo grep ‘temporary password’ /var/log/mysqld.log
---

Make a note of the password.

How to check your temporary MySQL root password.Configuring and Securing Your new MySQL installation comes with a security script to make securing configurations easier.

Launch the script with the following terminal command:

sudo mysql_secure_installation
---

The system will prompt you to enter the default root password. Enter the password you recovered earlier.

Next, the system will tell you that the password has expired, and prompt you to enter a new one. Enter a new password, make a note of it, then press Enter.

The system will rate your password strength, and ask if you want to enter a new, stronger password. If you’re satisfied with your password strength, hit the spacebar. To revise your password, press Y.

The Secure Installation script will continue, and you can safely reply "Y" to the rest of the prompts, which include:

```
Remove anonymous users
Disallow remote root login
Remove test database
Reload privilege tables

Note: If you receive an access denied error, see how to resolve the Access denied for user ‘root’@’localhost’ error.
```
To launch MySQL from the command line, use the command:

mysql -u root -p
---

The system will prompt you to enter your password. Enter the password you set in Step 6, and the system should respond by displaying the MySQL shell.

Once you’re done, you can log out with:

exit
---

The command prompt will change, indicating that you’ve logged out of MySQL.