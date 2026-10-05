
"""
Sistema SENTINEL: comprueba cada minuto si hay eventos nuevos en
sentinel_log y envía un correo de aviso por cada uno, según su tipo.
"""
 
import os
import time
 
import pymysql
import pymysql.cursors
import schedule
 
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
 
 
 

 
 
# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
db_servidor = "localhost"
db_usuario = "root"
db_password = "root"
db_nombre = "gestion"
 
sender_email = "facturacion@mail.com"
sender_password = os.environ.get("SENTINEL_SMTP_PASSWORD", "fffdsfsdsd")
 
 
# ---------------------------------------------------------------------------
# Conexión a la base de datos
# ---------------------------------------------------------------------------
def conectar():
    return pymysql.connect(
        host=db_servidor,
        user=db_usuario,
        password=db_password,
        database=db_nombre,
        charset="utf8",
        cursorclass=pymysql.cursors.DictCursor,
    )
 
 
# ---------------------------------------------------------------------------
# Destinatarios configurados para un tipo de alerta
# ---------------------------------------------------------------------------
def obtener_destinatarios(tipo_aviso):
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT mail FROM sentinel_mail WHERE codigo = %s", (tipo_aviso,)
            )
            resultado = cursor.fetchall()
        return [fila["mail"] for fila in resultado]
    finally:
        connection.close()
 
# ---------------------------------------------------------------------------
# Usuario (login) de un empleado, a partir de su código
# ---------------------------------------------------------------------------
def obtener_usuario_empleado(codigo_empleado):
    if not codigo_empleado:
        return ""
 
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT USUARIO FROM empleados_cab WHERE CODIGO = %s",
                (codigo_empleado,),
            )
            fila = cursor.fetchone()
        return fila["USUARIO"] if fila else ""
    finally:
        connection.close()
 
 
# ---------------------------------------------------------------------------
# Datos de un cliente (NIF, nombres y crédito asignado), a partir de su código
# ---------------------------------------------------------------------------
def obtener_datos_cliente(codigo_cliente):
    vacio = {
        "nif": "",
        "nombre_fiscal": "",
        "nombre_comercial": "",
        "credito_asignado": "",
    }
 
    if not codigo_cliente:
        return vacio
 
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT identificacion, NOMBRE1, NOMBRE2 FROM clientes_nmb WHERE CODIGO = %s",
                (codigo_cliente,),
            )
            nmb = cursor.fetchone()
 
            cursor.execute(
                "SELECT CREDITO FROM clientes_cre WHERE CODIGO = %s",
                (codigo_cliente,),
            )
            cre = cursor.fetchone()
 
        return {
            "nif": nmb["identificacion"] if nmb else "",
            "nombre_fiscal": nmb["NOMBRE1"] if nmb else "",
            "nombre_comercial": nmb["NOMBRE2"] if nmb else "",
            "credito_asignado": cre["CREDITO"] if cre else "",
        }
    finally:
        connection.close()
        

# ---------------------------------------------------------------------------
# Crédito ya consumido por un cliente (función credito_cli en MySQL).
# Es lenta, así que va aparte y solo se llama donde realmente hace falta
# (no en obtener_datos_cliente, para no afectar a alerta1 ni a futuras alertas).
# ---------------------------------------------------------------------------
def obtener_credito_consumido(codigo_cliente):
    if not codigo_cliente:
        return ""
 
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT credito_cli(%s) AS consumido", (codigo_cliente,))
            fila = cursor.fetchone()
        return fila["consumido"] if fila else ""
    finally:
        connection.close()
 
 
# ---------------------------------------------------------------------------
# Datos adicionales de un evento concreto (sentinel_dat), como {numero: valor}
# ---------------------------------------------------------------------------
def obtener_datos(codigo_log):
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT numero, valor FROM sentinel_dat WHERE codigo = %s ORDER BY numero",
                (codigo_log,),
            )
            filas = cursor.fetchall()
        return {fila["numero"]: fila["valor"] for fila in filas}
    finally:
        connection.close()
 
 
# ---------------------------------------------------------------------------
# Marca un evento como ya notificado
# ---------------------------------------------------------------------------
def marcar_notificado(codigo_log):
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sentinel_log SET notificado = TRUE WHERE codigo = %s",
                (codigo_log,),
            )
        connection.commit()
    finally:
        connection.close()
 
 
# ---------------------------------------------------------------------------
# Envío de correo
# ---------------------------------------------------------------------------
def enviar_correo(asunto, cuerpo, destinatarios, adjunto=None):
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
 
    if adjunto:
        with open(adjunto, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(adjunto)}"',
        )
        msg.attach(part)
 
    server = smtplib.SMTP("smtp.office365.com", 587)
    try:
        server.starttls()
        server.login(sender_email, sender_password)
 
        for destinatario in destinatarios:
            del msg["To"]
            msg["To"] = destinatario
            server.sendmail(sender_email, destinatario, msg.as_string())
 
        print(f"Correo enviado correctamente a: {', '.join(destinatarios)}")
    finally:
        server.quit()
 
 
# ---------------------------------------------------------------------------
# Composición de cada tipo de alerta.
# Cada función recibe la fila de sentinel_log (dict) y sus datos de
# sentinel_dat (dict {numero: valor}) y devuelve (asunto, cuerpo).
# ---------------------------------------------------------------------------
def alerta1(fila, datos):
    codigo_cliente = datos.get(1, "")
 
    usuario = obtener_usuario_empleado(fila["empleado"])
    cliente = obtener_datos_cliente(codigo_cliente)
 
    asunto = "🆕 AVISO SISTEMA: Cliente nuevo dado de alta"
 
    cuerpo = (
        "Se ha dado de alta un nuevo cliente en el sistema:\n"
        "\n"
        f"Usuario: {usuario}\n"
        f"Empleado: {fila['empleado']}\n"
        f"Fecha: {fila['fecha']}\n"
        f"Hora: {fila['hora']}\n"
        "\n"
        f"CODIGO: {codigo_cliente}\n"
        f"NIF: {cliente['nif']}\n"
        f"NOMBRE FISCAL / NOMBRE: {cliente['nombre_fiscal']}\n"
        f"NOMBRE COMERCIAL / APELLIDOS: {cliente['nombre_comercial']}\n"
        f"CRÉDITO ASIGNADO: {cliente['credito_asignado']}\n"
    )
 
    return asunto, cuerpo
 
 
def alerta2(fila, datos):
    venta = datos.get(1, "")
    codigo_cliente = datos.get(2, "")
    importe_venta = datos.get(3, "")
 
    usuario = obtener_usuario_empleado(fila["empleado"])
    cliente = obtener_datos_cliente(codigo_cliente)
    limite_credito = cliente["credito_asignado"]  # mismo dato, clientes_cre.CREDITO
    credito_consumido = obtener_credito_consumido(codigo_cliente)
 
    asunto = "⚠️ ALERTA SISTEMA: Venta a cliente que supera su crédito"
 
    cuerpo = (
        "Se ha registrado un albarán a un cliente que ha superado su crédito\n"
        "\n"
        f"Usuario: {usuario}\n"
        f"Empleado: {fila['empleado']}\n"
        f"Fecha: {fila['fecha']}\n"
        f"Hora: {fila['hora']}\n"
        "\n"
        f"CODIGO: {codigo_cliente}\n"
        f"NIF: {cliente['nif']}\n"
        f"NOMBRE FISCAL / NOMBRE: {cliente['nombre_fiscal']}\n"
        f"NOMBRE COMERCIAL / APELLIDOS: {cliente['nombre_comercial']}\n"
        f"CRÉDITO ASIGNADO: {cliente['credito_asignado']}\n"
        "\n"
        f"VENTA: {venta}\n"
        f"TIENDA: {fila['tienda']}\n"
        f"LIMITE DE CREDITO: {limite_credito}\n"
        f"CRÉDITO CONSUMIDO: {credito_consumido}\n"
    )
 
    return asunto, cuerpo
 
 
def alerta3(fila, datos):
    venta = datos.get(1, "")
    codigo_producto = datos.get(2, "")
    precio_costo = datos.get(3, "")
    precio_venta = datos.get(4, "")
 
    asunto = "📉 ALERTA SISTEMA: Venta de un producto por debajo del costo"
 
    cuerpo = (
        "Se ha registrado una venta de producto por debajo del costo\n"
        "\n"
        "Usuario:\n"
        f"Empleado: {fila['empleado']}\n"
        f"Fecha: {fila['fecha']}\n"
        f"Hora: {fila['hora']}\n"
        "\n"
        f"VENTA: {venta}\n"
        f"TIENDA: {fila['tienda']}\n"
        "IMPORTE VENTA:\n"
        f"PRODUCTO: {codigo_producto}\n"
        f"COSTO PRODUCTO: {precio_costo}\n"
        f"PRECIO VENDIDO: {precio_venta}\n"
    )
 
    return asunto, cuerpo
 
 
COMPOSITORES = {
    1: alerta1,
    2: alerta2,
    3: alerta3,
}
 
 
# ---------------------------------------------------------------------------
# Comprobación periódica: busca eventos pendientes y los notifica
# ---------------------------------------------------------------------------
def comprobar_alertas():
    connection = conectar()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sentinel_log WHERE NOT notificado ORDER BY fecha, hora"
            )
            pendientes = cursor.fetchall()
    finally:
        connection.close()
 
    if not pendientes:
        return
 
    print(f"Se encontraron {len(pendientes)} alertas no notificadas.")
 
    for fila in pendientes:
        tipo = fila["tipo"]
        compositor = COMPOSITORES.get(tipo)
 
        if compositor is None:
            print(f"Tipo {tipo} sin función de alerta definida (log {fila['codigo']}), se omite.")
            continue
 
        datos = obtener_datos(fila["codigo"])
        asunto, cuerpo = compositor(fila, datos)
 
        destinatarios = obtener_destinatarios(tipo)
        if not destinatarios:
            print(f"Sin destinatarios configurados para el tipo {tipo} (log {fila['codigo']}), se omite por ahora.")
            continue
 
        try:
            enviar_correo(asunto, cuerpo, destinatarios)
            marcar_notificado(fila["codigo"])
        except Exception as e:
            print(f"Error al procesar la alerta {fila['codigo']}: {e}")
 
 
# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        conexion_prueba = conectar()
        conexion_prueba.close()
        print(f"Conexión exitosa a la base de datos '{db_nombre}' en {db_servidor}.")
    except pymysql.MySQLError as e:
        print(f"Error al conectarse a la base de datos: {e}")
        raise SystemExit(1)
 
    print("Iniciando sistema de alertas SENTINEL...")
 
    schedule.every(20).seconds.do(comprobar_alertas)
 
    while True:
        schedule.run_pending()
        time.sleep(1)
