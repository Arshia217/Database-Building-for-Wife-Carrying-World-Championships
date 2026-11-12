-- =====================================================================
-- scripts/setup_access.sql
-- Grant database privileges for the Eukonkanto Web Application
-- Run as root or with sudo:
--   sudo mariadb < scripts/setup_access.sql   (or mysql -u root -p < scripts/setup_access.sql)
-- =====================================================================

-- 1. Create dedicated application user
CREATE USER IF NOT EXISTS 'eukakanto_user'@'localhost' IDENTIFIED BY 'eukakanto_pass';

-- 2. Grant permissions to create, drop, and manage the eukakanto database
GRANT ALL PRIVILEGES ON eukakanto.* TO 'eukakanto_user'@'localhost';
GRANT CREATE, DROP ON *.* TO 'eukakanto_user'@'localhost';

-- 3. Also grant passwordless unix_socket access to current OS user 'kartikeya'
CREATE USER IF NOT EXISTS 'kartikeya'@'localhost' IDENTIFIED VIA unix_socket;
GRANT ALL PRIVILEGES ON eukakanto.* TO 'kartikeya'@'localhost';
GRANT CREATE, DROP ON *.* TO 'kartikeya'@'localhost';

FLUSH PRIVILEGES;
