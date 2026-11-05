-- consultes_exemple.sql - Exemples per a DB Browser for SQLite (pestanya "Executa SQL").
-- Selecciona un bloc i prem Ctrl+Retorn. Les hores de la BD són UTC;
-- datetime(data_hora, 'localtime') les passa a l'hora del teu PC.

-- 1) Les darreres 20 lectures, amb hora local
SELECT datetime(data_hora, 'localtime') AS hora_local, lectura_ppm, lectura_brut,
       temperatura, humitat, rssi, snr
FROM lectures ORDER BY id DESC LIMIT 20;

-- 2) Mitjana, mínim i màxim per hora (UTC)
SELECT strftime('%Y-%m-%d %H:00', data_hora) AS hora_utc, COUNT(*) AS lectures,
       ROUND(AVG(temperatura), 1) AS temp_mitjana,
       MIN(temperatura) AS temp_min, MAX(temperatura) AS temp_max,
       ROUND(AVG(lectura_brut)) AS gas_brut_mitja
FROM lectures GROUP BY hora_utc ORDER BY hora_utc;

-- 3) Paquets perduts: salts al número de seqüència (0-255). Un reinici de la Pico o de
--    la RPi3 també hi apareix com a salt: no sempre és un paquet perdut de debò.
WITH ordenades AS (
    SELECT data_hora, seq, LAG(seq) OVER (ORDER BY id) AS anterior FROM lectures
)
SELECT datetime(data_hora, 'localtime') AS hora_local, anterior, seq,
       (seq - anterior + 256) % 256 - 1 AS perduts
FROM ordenades
WHERE anterior IS NOT NULL AND (seq - anterior + 256) % 256 <> 1;

-- 4) Una taula pròpia: anotacions d'esdeveniments (afegir una taula no afecta el sistema)
CREATE TABLE IF NOT EXISTS esdeveniments (
    id          INTEGER PRIMARY KEY,
    data_hora   TEXT NOT NULL,        -- UTC, com a lectures: '2026-11-01T12:00:00Z'
    descripcio  TEXT NOT NULL
);
INSERT INTO esdeveniments (data_hora, descripcio) VALUES ('2026-11-01T12:00:00Z', 'Calibratge del MQ-135');

-- 5) Una consulta desada com a vista (apareix com una taula; es consulta amb SELECT * FROM v_resum_diari)
CREATE VIEW IF NOT EXISTS v_resum_diari AS
SELECT substr(data_hora, 1, 10) AS dia_utc, COUNT(*) AS lectures,
       ROUND(AVG(temperatura), 1) AS temp_mitjana, MIN(temperatura) AS temp_min, MAX(temperatura) AS temp_max,
       ROUND(AVG(humitat), 1) AS hum_mitjana,
       ROUND(AVG(lectura_brut)) AS gas_brut_mitja
FROM lectures GROUP BY dia_utc;

-- 6) Lectures de l'hora següent a cada esdeveniment
SELECT e.descripcio, datetime(l.data_hora, 'localtime') AS hora_local, l.lectura_brut, l.temperatura
FROM esdeveniments e JOIN lectures l
  ON l.data_hora BETWEEN e.data_hora AND strftime('%Y-%m-%dT%H:%M:%SZ', e.data_hora, '+1 hour')
ORDER BY e.id, l.data_hora;
