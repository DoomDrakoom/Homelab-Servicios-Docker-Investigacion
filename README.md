# doomyyyserver — Servicios Docker

Documentación de los servicios self-hosted desplegados en el homelab, gestionados mediante contenedores Docker.

---

## 🦊 Gitea

**Categoría:** Control de versiones / Git

Servidor Git autoalojado, ligero y compatible con el flujo de trabajo de GitHub/GitLab. Permite alojar repositorios privados, gestionar issues, pull requests y wikis sin depender de servicios externos. Ideal para guardar proyectos personales, scripts de infraestructura o configuraciones (dotfiles, Docker Compose, etc.) manteniendo el control total de los datos.

---

## 📊 Grafana + Prometheus

**Categoría:** Monitorización y observabilidad

Stack de métricas para el homelab. **Prometheus** recopila y almacena series temporales (uso de CPU, RAM, red, estado de contenedores, etc.) mediante scraping periódico de exporters. **Grafana** consume esos datos y los representa en dashboards visuales e interactivos, con alertas configurables. Es la herramienta de referencia para tener visibilidad del estado y rendimiento de todo el servidor de un vistazo.

---

## 🏠 Homarr

**Categoría:** Dashboard / Panel de control

Página de inicio centralizada que agrupa accesos directos a todos los servicios del homelab en una única interfaz personalizable. Permite organizar aplicaciones en widgets, mostrar estado de contenedores en tiempo real e integrarse con otras herramientas (como Pi-hole o Uptime Kuma) para tener un "punto de entrada" único al servidor.

---

## 🎬 Jellyfin

**Categoría:** Media server

Alternativa open-source a Plex/Emby para gestionar y reproducir una biblioteca multimedia propia (películas, series, música) desde cualquier dispositivo de la red o remotamente. Sin telemetría, sin suscripciones y con transcodificación local, ofreciendo control total sobre el contenido.

---

## 🧃 Juice Shop

**Categoría:** Laboratorio de ciberseguridad

Aplicación web deliberadamente vulnerable desarrollada por OWASP, pensada para practicar pentesting web y aprender sobre vulnerabilidades reales (SQLi, XSS, IDOR, broken auth, etc.) en un entorno controlado y legal. Perfecta para formación en seguridad ofensiva y como banco de pruebas de herramientas de escaneo.

---

## 🔗 n8n

**Categoría:** Automatización / Workflows

Plataforma de automatización low-code que permite conectar servicios y crear flujos de trabajo (webhooks, APIs, notificaciones, integraciones con IA, etc.) mediante un editor visual de nodos. Se usa para automatizar tareas repetitivas del homelab o integrar servicios entre sí sin necesidad de escribir código desde cero.

---

## 🌐 NPM (Nginx Proxy Manager)

**Categoría:** Proxy inverso / Gestión de red

Interfaz web sobre Nginx que simplifica la configuración de proxys inversos, certificados SSL (Let's Encrypt automático) y redirecciones de dominios/subdominios hacia los distintos servicios del servidor. Es la pieza que permite acceder a cada contenedor mediante una URL propia y segura (HTTPS) sin exponer puertos directamente.

---

## 🚫 Pi-hole

**Categoría:** DNS / Bloqueo de publicidad

Servidor DNS que actúa como sumidero (*sinkhole*) para bloquear anuncios, trackers y dominios maliciosos a nivel de red, protegiendo todos los dispositivos conectados sin necesidad de extensiones en cada uno. También ofrece estadísticas detalladas de las consultas DNS realizadas en la red doméstica.

---

## 📡 Uptime Kuma

**Categoría:** Monitorización de disponibilidad

Herramienta de monitoreo de uptime que comprueba periódicamente si los servicios (HTTP, TCP, DNS, etc.) están activos y responden correctamente. Genera alertas (Telegram, Discord, email...) ante caídas y ofrece páginas de estado públicas o privadas, siendo el "vigilante" que avisa cuando algo falla en el servidor.

---

## 📄 README.md

Este mismo archivo, con la documentación general del stack de servicios del servidor.
