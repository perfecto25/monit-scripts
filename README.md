# Monit sample scripts and rule sets

full description here

https://perfecto25.medium.com/monit-alert-system-config-examples-a7967d6a1e1f


## setup Monit agents

create "monit" service account with /home/monit

create /etc/monit directory

add symlink

ln -s /etc/monit/monit.conf /home/monit/.monitrc

add any sudoers rules that monit agent may need (restart service, read file, etc)


    vi /etc/sudoers.d/monit

    %monit ALL=(ALL) NOPASSWD: /usr/bin/find
    %monit ALL=(root) NOPASSWD: /bin/systemctl restart httpd
    %monit ALL=(root) NOPASSWD: /bin/ls /proc/*
    %monit ALL=(root) NOPASSWD: /bin/cat /proc/*
