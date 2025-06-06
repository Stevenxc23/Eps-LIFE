CREATE DATABASE IF NOT EXISTS EPS;
USE EPS;

-- Tabla de usuarios
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100),
    correo VARCHAR(100) UNIQUE,
    contrasena VARCHAR(255),
    rol ENUM('paciente', 'medico', 'admin') NOT NULL
);

-- Tabla de citas
CREATE TABLE citas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT,
    id_medico INT,
    fecha DATE,
    hora TIME,
    estado ENUM('pendiente', 'confirmada', 'cancelada') DEFAULT 'pendiente',
    FOREIGN KEY (id_paciente) REFERENCES usuarios(id),
    FOREIGN KEY (id_medico) REFERENCES usuarios(id)
);

-- Tabla de horarios médicos
CREATE TABLE horarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_medico INT,
    fecha DATE,
    hora_inicio TIME,
    hora_fin TIME,
    disponible BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_medico) REFERENCES usuarios(id)
);