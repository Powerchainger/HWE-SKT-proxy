1. Find default gateway
On OSX:
```bash
$ route get default | grep gateway
```

Linux (tested on Ubuntu):
```bash
$ ip r | grep ^def
```

2. Scan network for hosts (DO NOT DO THIS ON OTHER NETWORKS THAN YOUR OWN, THIS IS NETWORK SCANNING IS ILLEGAL)
```bash
$ nmap 192.168.0.1/24
```

3. Search for ip address of Raspberry. You can recognize it by the open ports (only port 22 for ssh by default)
```bash
$ ssh ubuntu@192.168.0.102
```

4. Login with password

5. Create docker-compose file
Use sudo when you get errors like this:
ERROR: Couldn't connect to Docker daemon at http+docker://localhost - is it running?

```
$ touch docker-compose.yml
```

6. Copy docker-compose content from HWE-SKT-proxy

7. Remove "build" argument in docker-compose config

8. Add .env file by copying .env.example
```bash
$ touch .env
```

9. FIll the .env file with the correct values
(Use nano or vim to edit the file)

10. Pull images
```bash
$ sudo docker-compose pull
```

11. Start application
```bash
$ sudo docker-compose up
```

12. Connect energy socket by holding the button until it blinks blue, then connect to the wifi of the energy socket using the Homewizard Energy app.