1. Find default gateway
```
route get default | grep gateway
```

2. 
```
nmap -sP 192.168.0.1/24
```

3. Found e.g. 192.168.0.102
```
ssh ubuntu@192.168.0.102
```

4. Login with password

5. Create docker-compose file
```
touch docker-compose.yml
```

6. Copy docker-compose content from HWE-SKT-proxy

7. Start application
```
sudo docker-compose up
```

8. Connect energy socket by holding the button until it blinks blue, then connect to the wifi of the energy socket using the Homewizard Energy app.