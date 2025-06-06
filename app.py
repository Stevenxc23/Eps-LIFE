import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from functools import wraps
from fpdf import FPDF
import mysql.connector
from flask import make_response
import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configurar conexión a la base de datos
conn = mysql.connector.connect(
    conn = mysql.connector.connect(
    host="db4free.net",
    user="steven12",
    password="steven123",
    database="epsdb123"
)
)
cursor = conn.cursor(dictionary=True)

# Decoradores de seguridad
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def verificar_rol(rol_requerido):
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'rol' not in session or session['rol'] != rol_requerido:
                return "Acceso denegado: rol incorrecto."
            return f(*args, **kwargs)
        return wrapper
    return decorador

# Rutas
@app.route('/inicio')
def inicio():
    return render_template('inicio.html')

@app.route('/')
def index():
    return redirect(url_for('inicio'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        cursor.execute("SELECT * FROM usuarios WHERE correo=%s AND contrasena=%s", (correo, contrasena))
        usuario = cursor.fetchone()
        if usuario:
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            return redirect(url_for('home'))
        return "Credenciales incorrectas."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        rol = request.form['rol']
        cursor.execute("INSERT INTO usuarios (nombre, correo, contrasena, rol) VALUES (%s, %s, %s, %s)",
                       (nombre, correo, contrasena, rol))
        conn.commit()
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/home')
@login_required
def home():
    usuario_id = session.get('usuario_id')
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
    usuario = cursor.fetchone()

    return render_template('home.html', usuario=usuario)

@app.route('/agendar_cita', methods=['GET', 'POST'])
@login_required
@verificar_rol('paciente')
def agendar_cita():
    if request.method == 'POST':
        id_paciente = session['usuario_id']
        id_medico = request.form['id_medico']
        fecha = request.form['fecha']
        hora = request.form['hora']
        cursor.execute("""
            SELECT * FROM horarios 
            WHERE id_medico = %s 
              AND dia = DAYNAME(%s)
              AND %s BETWEEN hora_inicio AND hora_fin
        """, (id_medico, fecha, hora))
        horario_disponible = cursor.fetchone()

        if not horario_disponible:
            return "El médico no está disponible en ese horario."

        cursor.execute("SELECT * FROM citas WHERE id_medico=%s AND fecha=%s AND hora=%s",
                       (id_medico, fecha, hora))
        if cursor.fetchone():
            return "Esa hora ya está ocupada."

        cursor.execute("INSERT INTO citas (id_paciente, id_medico, fecha, hora) VALUES (%s, %s, %s, %s)",
                       (id_paciente, id_medico, fecha, hora))
        conn.commit()
        return redirect(url_for('ver_citas'))

    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol='medico'")
    medicos = cursor.fetchall()
    return render_template('agendar_cita.html', medicos=medicos)

@app.route('/ver_citas')
@login_required
@verificar_rol('paciente')
def ver_citas():
    id_paciente = session['usuario_id']
    cursor.execute("""
        SELECT c.fecha, c.hora, c.estado, m.nombre AS medico
        FROM citas c
        JOIN usuarios m ON c.id_medico = m.id
        WHERE c.id_paciente = %s
        ORDER BY c.fecha DESC
    """, (id_paciente,))
    citas = cursor.fetchall()
    return render_template('ver_citas.html', citas=citas)

@app.route('/configurar_horarios', methods=['GET', 'POST'])
@login_required
@verificar_rol('medico')
def configurar_horarios():
    id_medico = session['usuario_id']
    if request.method == 'POST':
        dia = request.form['dia']  # día de la semana
        inicio = request.form['hora_inicio']
        fin = request.form['hora_fin']
        cursor.execute("""
            INSERT INTO horarios (id_medico, dia, hora_inicio, hora_fin)
            VALUES (%s, %s, %s, %s)
        """, (id_medico, dia, inicio, fin))
        conn.commit()
        return redirect(url_for('configurar_horarios'))
    cursor.execute("SELECT * FROM horarios WHERE id_medico = %s", (id_medico,))
    horarios = cursor.fetchall()
    return render_template('configurar_horarios.html', horarios=horarios)

@app.route('/dashboard/admin')
@login_required
@verificar_rol('admin')
def dashboard_admin():
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
    SELECT 
        citas.id,
        citas.fecha,
        citas.hora,
        citas.estado,
        paciente.nombre AS nombre_paciente,
        medico.nombre AS nombre_medico
    FROM citas
    JOIN usuarios AS paciente ON citas.id_paciente = paciente.id
    JOIN usuarios AS medico ON citas.id_medico = medico.id
                   """)
    citas = cursor.fetchall()


    cursor.execute("SELECT COUNT(*) AS total FROM citas WHERE estado = 'pendiente'")
    resultado = cursor.fetchone()
    citas_pendientes = resultado['total'] if resultado else 0

    cursor.execute("SELECT COUNT(*) AS total FROM citas WHERE estado = 'confirmada'")
    resultado = cursor.fetchone()
    citas_confirmadas = resultado['total'] if resultado else 0

    return render_template('dashboard_admin.html', citas=citas, citas_pendientes=citas_pendientes, citas_confirmadas=citas_confirmadas)

@app.route('/exportar_citas_pdf')
@login_required
def exportar_citas_pdf():
    usuario_id = session['usuario_id']
    rol = session['rol']

    if rol == 'paciente':
        cursor.execute("""
            SELECT c.id, u.nombre AS medico, c.fecha, c.hora 
            FROM citas c 
            JOIN usuarios u ON c.id_medico = u.id 
            WHERE c.id_paciente = %s
        """, (usuario_id,))
    elif rol == 'medico':
        cursor.execute("""
            SELECT c.id, u.nombre AS paciente, c.fecha, c.hora 
            FROM citas c 
            JOIN usuarios u ON c.id_paciente = u.id 
            WHERE c.id_medico = %s
        """, (usuario_id,))
    else:
        cursor.execute("""
            SELECT c.id, p.nombre AS paciente, m.nombre AS medico, c.fecha, c.hora 
            FROM citas c 
            JOIN usuarios p ON c.id_paciente = p.id 
            JOIN usuarios m ON c.id_medico = m.id
        """)

    citas = cursor.fetchall()

    class PDF(FPDF):
        def header(self):
            try:
                self.image('static/logo.png', 10, 8, 20)
            except:
                pass
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, 'EPS - Reporte de Citas Médicas', ln=True, align='C')
            self.set_font('Arial', '', 10)
            self.cell(0, 10, f'Generado el: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', ln=True, align='C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', align='C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)

    if rol == 'admin':
        pdf.cell(20, 10, 'ID', 1)
        pdf.cell(50, 10, 'Paciente', 1)
        pdf.cell(50, 10, 'Médico', 1)
        pdf.cell(35, 10, 'Fecha', 1)
        pdf.cell(25, 10, 'Hora', 1)
        pdf.ln()
        for c in citas:
            pdf.set_font('Arial', '', 11)
            pdf.cell(20, 10, str(c['id']), 1)
            pdf.cell(50, 10, c['paciente'], 1)
            pdf.cell(50, 10, c['medico'], 1)
            pdf.cell(35, 10, str(c['fecha']), 1)
            pdf.cell(25, 10, str(c['hora']), 1)
            pdf.ln()
    else:
        pdf.cell(20, 10, 'ID', 1)
        pdf.cell(80, 10, 'Nombre', 1)
        pdf.cell(40, 10, 'Fecha', 1)
        pdf.cell(30, 10, 'Hora', 1)
        pdf.ln()
        for c in citas:
            pdf.set_font('Arial', '', 11)
            pdf.cell(20, 10, str(c['id']), 1)
            nombre = c['medico'] if rol == 'paciente' else c['paciente']
            pdf.cell(80, 10, nombre, 1)
            pdf.cell(40, 10, str(c['fecha']), 1)
            pdf.cell(30, 10, str(c['hora']), 1)
            pdf.ln()

    pdf.ln(10)
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 10, 'Este reporte es generado automáticamente por el sistema de la EPS.', ln=True, align='C')

    response = make_response(pdf.output(dest='S').encode('latin1'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=citas_eps.pdf'
    return response



if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=os.environ.get('PORT', 5000))

