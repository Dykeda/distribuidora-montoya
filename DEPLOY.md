
# Guía de despliegue: publicar Distribuidora Montoya en línea (VPS + DuckDNS)

Esta guía la sigues tú (Kevin) una sola vez para poner el sistema en una URL accesible
desde cualquier lugar, con HTTPS real (candado, sin advertencias del navegador). Después
de esto, el dueño solo necesita un navegador, la URL y la contraseña.

Usamos:
- **DigitalOcean** — un servidor virtual (VPS) propio, ~$6/mes, sin límites raros de CPU
  ni "modo dormido". Tú tienes control total.
- **DuckDNS** — un subdominio gratis (ej. `distribuidoramontoya.duckdns.org`) que apunta a
  la IP de tu servidor, necesario para tener HTTPS real con Certbot.
- **GitHub** — para subir el código y poder actualizarlo después con un comando.

> Nota: esto reemplaza el intento anterior con PythonAnywhere (se sintió muy complicado y
> se descartó). Este camino cuesta unos dólares al mes, pero es más simple de mantener:
> no se duerme, no hay límite de CPU diario, y el archivo de la base de datos vive
> siempre en el mismo lugar.

## 1. Crear el droplet en DigitalOcean

1. Crea una cuenta en [digitalocean.com](https://www.digitalocean.com/).
2. **Create → Droplets**:
   - Imagen: **Ubuntu 24.04 (LTS) x64**
   - Plan: **Basic**, la opción más barata (~$6/mes, 1 GB RAM es de sobra para esta app)
   - Datacenter: el más cercano a donde vive tu papá
   - Autenticación: **SSH key** (más seguro que contraseña — DigitalOcean te guía para
     generarla y subirla si no tienes una todavía)
3. Anota la **IP pública** del droplet una vez creado (algo como `164.90.XX.XX`).

## 2. Crear el subdominio en DuckDNS

1. Entra a [duckdns.org](https://www.duckdns.org/) e inicia sesión (con GitHub o Google).
2. Crea un subdominio, por ejemplo `distribuidoramontoya` (queda como
   `distribuidoramontoya.duckdns.org`).
3. En el campo de IP, pon la IP pública de tu droplet (paso 1) y dale **update ip**.
   Como el droplet tiene IP fija, no hace falta configurar actualización automática —
   se pone una vez y ya.

## 3. Subir el código a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no tienes una.
2. Crea un repositorio nuevo **privado** llamado `distribuidora-montoya` (sin README, sin
   .gitignore — ya los tenemos en el proyecto).
3. Pásame la URL del repositorio vacío (algo como
   `https://github.com/TU-USUARIO/distribuidora-montoya.git`) y yo conecto el remoto y
   subo el código desde aquí (te confirmo antes de hacer el `git push`).

## 4. Conectarte por SSH y preparar el servidor

```bash
ssh root@TU-IP-PUBLICA
```

Instala lo necesario y crea un usuario sin privilegios de root para correr la app:

```bash
apt update && apt upgrade -y
apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git ufw

adduser montoya
usermod -aG sudo montoya
su - montoya
```

## 5. Clonar el proyecto

Como el repositorio es privado, necesitas un token de acceso:
- En GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained
  tokens → Generate new token**. Acceso de **solo lectura** ("Contents: Read-only")
  limitado al repositorio `distribuidora-montoya`. Copia el token (solo se muestra una
  vez).

```bash
cd ~
git clone https://TU-TOKEN@github.com/TU-USUARIO/distribuidora-montoya.git
cd distribuidora-montoya
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## 6. Variables de entorno

Crea el archivo `/home/montoya/distribuidora-montoya.env` con **valores propios** (nunca
los de por defecto del código):

```bash
cat > ~/distribuidora-montoya.env << 'EOF'
APP_PASSWORD=ELIGE-UNA-CONTRASEÑA-SEGURA
SECRET_KEY=UNA-CADENA-LARGA-Y-ALEATORIA-CUALQUIERA
FORZAR_HTTPS=true
EOF
```

(Puedes generar una cadena aleatoria para `SECRET_KEY` con `openssl rand -hex 32`.)

## 7. Crear la base de datos

```bash
cd ~/distribuidora-montoya
venv/bin/flask --app app init-db
```

## 8. Servicio systemd (gunicorn)

Copia el archivo que ya viene en el repo:

```bash
sudo cp ~/distribuidora-montoya/deploy/distribuidora-montoya.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now distribuidora-montoya
sudo systemctl status distribuidora-montoya   # debe decir "active (running)"
```

## 9. Nginx + HTTPS con Certbot

```bash
sudo cp ~/distribuidora-montoya/deploy/nginx.conf /etc/nginx/sites-available/distribuidora-montoya
sudo sed -i 's/TU-SUBDOMINIO/distribuidoramontoya/' /etc/nginx/sites-available/distribuidora-montoya
sudo ln -s /etc/nginx/sites-available/distribuidora-montoya /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx -d distribuidoramontoya.duckdns.org
```

Certbot te va a preguntar un correo y si quieres redirigir HTTP a HTTPS automáticamente
— di que sí. Certbot también configura la renovación automática del certificado, no hay
que hacer nada más por eso.

## 10. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 11. Probar

Abre `https://distribuidoramontoya.duckdns.org` (con tu subdominio real) — debe verse el
candado sin advertencias, y pedir la contraseña que pusiste en el paso 6. Comparte esa
URL y la contraseña con tu papá.

## 12. Respaldo automático de la base de datos

```bash
chmod +x ~/distribuidora-montoya/deploy/respaldar_servidor.sh
crontab -e
```

Agrega esta línea (respaldo diario a las 3 AM):
```
0 3 * * * /home/montoya/distribuidora-montoya/deploy/respaldar_servidor.sh
```

Los respaldos quedan en `~/respaldos/`, con fecha en el nombre, y se conservan los
últimos 30 días. De vez en cuando, baja una copia a tu propio computador como respaldo
extra fuera del servidor:

```bash
scp montoya@TU-IP-PUBLICA:~/respaldos/distribuidora_2026-08-12.db .
```

## Para actualizar el código más adelante

1. En tu computador: pídeme el cambio, yo hago `git push` a `origin` como siempre.
2. En el servidor (por SSH):
   ```bash
   cd ~/distribuidora-montoya
   git pull
   venv/bin/pip install -r requirements.txt   # solo si cambiaron las dependencias
   sudo systemctl restart distribuidora-montoya
   ```

## Si algo no carga

```bash
sudo systemctl status distribuidora-montoya   # ¿está corriendo gunicorn?
sudo journalctl -u distribuidora-montoya -n 50   # últimas líneas de error
sudo nginx -t                                  # ¿la config de nginx es válida?
sudo tail -n 50 /var/log/nginx/error.log
```
