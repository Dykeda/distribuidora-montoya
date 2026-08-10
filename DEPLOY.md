# Guía de despliegue: publicar Distribuidora Montoya en línea

Esta guía la sigues tú (Kevin) una sola vez para poner el sistema en una URL accesible
desde cualquier lugar. Después de esto, el dueño solo necesita un navegador y la
contraseña — nada de instalar Python ni correr `.bat`.

Usamos **PythonAnywhere** (hosting gratis para Flask, siempre encendido, sin tarjeta de
crédito) y **GitHub** (para subir el código y poder actualizarlo después con un comando).

## 1. Subir el código a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no tienes una.
2. Crea un repositorio nuevo **privado** llamado `distribuidora-montoya` (sin README, sin
   .gitignore — ya los tenemos).
3. En este proyecto, conéctalo como remoto y sube el código:
   ```
   git remote add origin https://github.com/TU-USUARIO/distribuidora-montoya.git
   git push -u origin master
   ```

## 2. Crear la cuenta en PythonAnywhere

1. Regístrate gratis en [pythonanywhere.com](https://www.pythonanywhere.com/registration/register/beginner/)
   (cuenta "Beginner", sin costo).

## 3. Clonar el proyecto y crear el entorno virtual

1. Abre una **consola Bash** desde el dashboard de PythonAnywhere.
2. Crea el entorno virtual:
   ```
   mkvirtualenv --python=/usr/bin/python3.13 montoya-venv
   ```
3. Como el repositorio es privado, necesitas un token de acceso para clonarlo:
   - En GitHub: Settings → Developer settings → Personal access tokens → Fine-grained
     tokens → Generate new token. Dale acceso de **solo lectura** ("Contents:
     Read-only") limitado al repositorio `distribuidora-montoya`. Copia el token (solo
     se muestra una vez).
   - En la consola de PythonAnywhere:
     ```
     git clone https://TU-TOKEN@github.com/TU-USUARIO/distribuidora-montoya.git
     cd distribuidora-montoya
     pip install -r requirements.txt
     ```

## 4. Crear la web app

1. Ve a la pestaña **Web** → **Add a new web app** → elige **Manual configuration** →
   Python 3.13 (la misma versión del entorno virtual).
2. En la sección **Virtualenv**, escribe `montoya-venv` (PythonAnywhere completa la ruta
   sola).
3. En **Code → WSGI configuration file**, haz clic para editarlo, borra todo su
   contenido y reemplázalo por:
   ```python
   import sys, os

   path = '/home/TU-USUARIO/distribuidora-montoya'
   if path not in sys.path:
       sys.path.insert(0, path)

   # Cambia estos dos valores por los tuyos — nunca dejes los que vienen por defecto.
   os.environ['APP_PASSWORD'] = 'ELIGE-UNA-CONTRASEÑA-SEGURA'
   os.environ['SECRET_KEY'] = 'una-cadena-larga-y-aleatoria-cualquiera'

   from app import app as application
   ```
   (Reemplaza `TU-USUARIO` por tu nombre de usuario de PythonAnywhere en ambos lugares.)

## 5. Crear la base de datos

En la consola Bash (con el entorno activado — si no, `workon montoya-venv`):
```
cd distribuidora-montoya
python -c "from app import app; from extensions import db; app.app_context().push(); db.create_all()"
```

## 6. Activar

1. Vuelve a la pestaña **Web** y presiona el botón verde **Reload**.
2. Abre `https://TU-USUARIO.pythonanywhere.com` — debe pedir la contraseña que pusiste en
   el paso 4. Al ingresarla, debe verse el dashboard vacío, listo para usar.
3. Comparte esa URL y la contraseña con tu papá.

## Para actualizar el código más adelante

Cuando hagas cambios y quieras subirlos:
1. En tu computador: `git push` (a `origin`, como siempre).
2. En la consola Bash de PythonAnywhere:
   ```
   cd distribuidora-montoya
   git pull
   ```
3. Pestaña **Web** → botón **Reload**.

## Respaldo de los datos

PythonAnywhere no tiene integración con OneDrive como tu computador local, así que
`respaldar.bat` no aplica ahí. Por ahora, de vez en cuando entra a la pestaña **Files**
de PythonAnywhere y descarga manualmente `distribuidora-montoya/instance/distribuidora.db`
a tu computador como respaldo. Si esto se vuelve tedioso, se puede automatizar más
adelante (por ejemplo con el "scheduled task" diario que incluye la cuenta gratis).
