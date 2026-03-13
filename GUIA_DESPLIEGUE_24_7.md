# GUÍA DE DESPLIEGUE CLOUD (OPERACIÓN 24/7) - Versión 2.5

Para que tu bot funcione sin que tu computadora esté encendida y pueda ejecutar compras/ventas automáticamente el 100% del tiempo, debes alojarlo en la nube.

## 🚀 OPCIÓN 1: Streamlit Cloud (Gratis y Rápida)
Ideal para visualizar y probar. Se conecta a tu GitHub.

**Pasos:**
1. Sube tu código a GitHub.
2. Entra en [share.streamlit.io](https://share.streamlit.io).
3. Conecta tu repositorio.
4. **IMPORTANTE:** Para que no pida tus llaves cada vez, usa el menú **"Secrets"** en la configuración de Streamlit Cloud para guardar tus llaves como variables de entorno (opcional) o pégalas manualmente en la sidebar una vez desplegado.

---

## 🛰️ OPCIÓN 2: VPS (DigitalOcean, AWS, Google Cloud) - MÁS ESTABLE
Un VPS es un mini-servidor Linux que nunca se apaga. Es lo que usan los traders profesionales.

### Configuración Ganadora con PM2:
Si quieres que el escaner de 60 segundos **NUNCA** se detenga aunque cierres la pestaña:

1. **Instalar PM2** (Process Manager):
   ```bash
   sudo npm install -g pm2
   ```
2. **Lanzar el Bot:**
   ```bash
   pm2 start "streamlit run app.py --server.port 80" --name "trading-terminal"
   ```
3. **Persistencia:**
   ```bash
   pm2 save
   pm2 startup
   ```
Con esto, si el servidor se reinicia por mantenimiento, el bot vuelve a encenderse solo.

---

## 🔒 SEGURIDAD Y MEJORES PRÁCTICAS

1. **API Keys:** Nunca las dejes escritas directamente en el código (`app.py`). La versión actual tiene campos vacíos por seguridad. Siempre ingrésalas por la interfaz de usuario o usa variables de entorno.
2. **Modo Paper:** Siempre inicia en **Modo Paper Trading** el primer par de días en la nube para asegurar que la conexión de internet del servidor no afecte las órdenes.
3. **Monto Fraccionario:** Gracias a la versión 2.5, puedes probar en la nube con solo **$1 USD** por operación para verificar que el servidor esté ejecutando bien antes de subir el monto.

---

## 📈 MONITOREO DESDE EL CELULAR
Como Streamlit es responsive, puedes entrar al link de tu servidor desde el navegador de tu celular y ver las gráficas y el historial de trades en tiempo real mientras estás en la calle.

---
**Trading Pro System** - Resiliencia y Estabilidad en la Nube.
