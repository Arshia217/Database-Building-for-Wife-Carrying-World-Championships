-- =====================================================================
-- schema.sql  |  Wife Carrying World Championships (Eukonkanto)
-- Paradigm: Relational | DBMS: MySQL 8.0 (InnoDB)
-- Run with:  mysql -u <user> -p < schema.sql
-- Base design: Team 7 Phase 3 (3NF) of Team 16 Phase 2 EER.
-- Revisions to Phase 3 are marked  [REVISION Rn]  and go in README
-- R1/R2: stronger foreign keys.  R3-R7: columns the website does not publish
-- may be NULL (Phase 1 'Assumption' allows attributes that can return NULL).
-- "Design Changes". Assumptions are marked  [ASSUMPTION]  .
-- =====================================================================

-- 1. drop any existing copy and create afresh
DROP DATABASE IF EXISTS eukakanto;
CREATE DATABASE eukakanto CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 2. switch to it
USE eukakanto;

-- 3. structures ---------------------------------------------------------

CREATE TABLE country (
    country_code  CHAR(3)       NOT NULL,
    country_name  VARCHAR(80)   NOT NULL,
    region        VARCHAR(60)   NULL,
    PRIMARY KEY (country_code),
    UNIQUE KEY uq_country_name (country_name)
) ENGINE=InnoDB;

CREATE TABLE participant (
    participant_id  INT           NOT NULL AUTO_INCREMENT,
    first_name      VARCHAR(50)   NOT NULL,
    last_name       VARCHAR(50)   NULL,        -- [REVISION R4] website sometimes shows only a first name
    date_of_birth   DATE          NULL,        -- [REVISION R3] not published on the website
    weight_kg       DECIMAL(5,2)  NULL    ,
    country_code    CHAR(3)       NOT NULL,
    approval_status ENUM('Pending', 'Approved', 'None') NOT NULL DEFAULT 'Approved',
    PRIMARY KEY (participant_id),
    KEY idx_participant_name (last_name, first_name),
    CONSTRAINT chk_participant_weight CHECK (weight_kg > 0),
    CONSTRAINT fk_participant_country FOREIGN KEY (country_code)
        REFERENCES country (country_code)
        ON UPDATE CASCADE ON DELETE RESTRICT          -- D2: cannot delete a country in use
) ENGINE=InnoDB;

CREATE TABLE participant_contact (                    -- multivalued contact_numbers
    participant_id  INT          NOT NULL,
    contact_number  VARCHAR(20)  NOT NULL,
    PRIMARY KEY (participant_id, contact_number),
    CONSTRAINT fk_pc_participant FOREIGN KEY (participant_id)
        REFERENCES participant (participant_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE category (
    category_id            INT           NOT NULL AUTO_INCREMENT,
    category_name          VARCHAR(80)   NOT NULL,
    eligibility_rules      TEXT          NULL,
    race_rules             TEXT          NULL,
    track_description      TEXT          NULL,
    minimum_age            INT NULL,
    maximum_age            INT NULL,
    min_carried_weight_kg  DECIMAL(5,2)  NULL,
    PRIMARY KEY (category_id),
    UNIQUE KEY uq_category_name (category_name),
    CONSTRAINT chk_category_age CHECK
        (minimum_age IS NULL OR maximum_age IS NULL OR minimum_age <= maximum_age),
    CONSTRAINT chk_category_weight CHECK
        (min_carried_weight_kg IS NULL OR min_carried_weight_kg > 0)
) ENGINE=InnoDB;

CREATE TABLE category_alias (                         -- multivalued aliases
    category_id  INT           NOT NULL,
    alias        VARCHAR(60)   NOT NULL,
    PRIMARY KEY (category_id, alias),
    CONSTRAINT fk_ca_category FOREIGN KEY (category_id)
        REFERENCES category (category_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE competition_edition (
    edition_year    SMALLINT      NOT NULL,
    start_date      DATE          NOT NULL,
    end_date        DATE          NOT NULL,
    venue           VARCHAR(120)  NOT NULL,
    edition_status  ENUM('Scheduled','Ongoing','Completed','Cancelled')
                    NOT NULL DEFAULT 'Scheduled',
    PRIMARY KEY (edition_year),
    CONSTRAINT chk_edition_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_edition_year  CHECK (edition_year > 0)
) ENGINE=InnoDB;

CREATE TABLE has_category (                           -- R2
    edition_year  SMALLINT  NOT NULL,
    category_id   INT       NOT NULL,
    PRIMARY KEY (edition_year, category_id),
    CONSTRAINT fk_hc_edition FOREIGN KEY (edition_year)
        REFERENCES competition_edition (edition_year)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_hc_category FOREIGN KEY (category_id)
        REFERENCES category (category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE participates_in_edition (                -- R12 (derivable, kept per Phase 3)
    participant_id  INT       NOT NULL,
    edition_year    SMALLINT  NOT NULL,
    PRIMARY KEY (participant_id, edition_year),
    CONSTRAINT fk_pie_participant FOREIGN KEY (participant_id)
        REFERENCES participant (participant_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pie_edition FOREIGN KEY (edition_year)
        REFERENCES competition_edition (edition_year)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE competition_entry (
    entry_id             INT           NOT NULL AUTO_INCREMENT,
    entry_name           VARCHAR(100)  NULL,
    bib_number           INT           NULL,       -- [REVISION R5] bibs of 2024/2025 winners are not published
    registration_status  ENUM('Pending','Approved','Withdrawn')
                         NOT NULL DEFAULT 'Pending',
    registration_time    TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    edition_year         SMALLINT      NOT NULL,
    category_id          INT           NOT NULL,
    PRIMARY KEY (entry_id),
    UNIQUE KEY uq_entry_bib (edition_year, category_id, bib_number),     -- alternate key
    UNIQUE KEY uq_entry_edition (entry_id, edition_year),                -- [REVISION R1] target of composite FKs
    KEY idx_entry_name (entry_name),
    CONSTRAINT chk_entry_bib CHECK (bib_number > 0),
    -- [REVISION R2] R3+R4 enforced together: the category must be offered in that edition (R2)
    CONSTRAINT fk_entry_edition_category FOREIGN KEY (edition_year, category_id)
        REFERENCES has_category (edition_year, category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE pair_entry (                             -- subclass (disjoint, total)
    entry_id    INT  NOT NULL,
    carrier_id  INT  NOT NULL,
    carried_id  INT  NOT NULL,
    PRIMARY KEY (entry_id),
    CONSTRAINT chk_pair_distinct CHECK (carrier_id <> carried_id),
    CONSTRAINT fk_pair_entry FOREIGN KEY (entry_id)
        REFERENCES competition_entry (entry_id) ON UPDATE CASCADE ON DELETE CASCADE,
    -- ON UPDATE RESTRICT (not CASCADE): MySQL does not allow a CHECK on a column
    -- that has a CASCADE rule (error 3823). Participant ids never change anyway.
    CONSTRAINT fk_pair_carrier FOREIGN KEY (carrier_id)
        REFERENCES participant (participant_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_pair_carried FOREIGN KEY (carried_id)
        REFERENCES participant (participant_id) ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE team_entry (                             -- subclass (disjoint, total)
    entry_id   INT           NOT NULL,
    team_name  VARCHAR(150)  NOT NULL,
    PRIMARY KEY (entry_id),
    CONSTRAINT fk_team_entry FOREIGN KEY (entry_id)
        REFERENCES competition_entry (entry_id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE participates_in (                        -- R5
    entry_id          INT  NOT NULL,
    participant_id    INT  NOT NULL,
    participant_role  ENUM('Carrier','Carried') NOT NULL,
    PRIMARY KEY (entry_id, participant_id),
    CONSTRAINT fk_pi_entry FOREIGN KEY (entry_id)
        REFERENCES competition_entry (entry_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pi_participant FOREIGN KEY (participant_id)
        REFERENCES participant (participant_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE wins (                                   -- R11
    entry_id      INT       NOT NULL,
    edition_year  SMALLINT  NOT NULL,
    PRIMARY KEY (entry_id),
    -- [REVISION R1] guarantees the winning edition = the entry's own edition (K2)
    CONSTRAINT fk_wins_entry FOREIGN KEY (entry_id, edition_year)
        REFERENCES competition_entry (entry_id, edition_year)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_wins_edition FOREIGN KEY (edition_year)
        REFERENCES competition_edition (edition_year)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE race (                                   -- weak, owner = edition (R6)
    edition_year    SMALLINT     NOT NULL,
    race_no         SMALLINT     NOT NULL,
    race_date       DATE         NOT NULL,
    race_type       ENUM('Sprint','Heat','Final','Other') NOT NULL,
    scheduled_time  TIME         NULL,
    race_status     ENUM('Scheduled','Ongoing','Completed','Cancelled')
                    NOT NULL DEFAULT 'Scheduled',
    is_published    BOOLEAN      NOT NULL DEFAULT FALSE,
    category_id     INT          NOT NULL,
    PRIMARY KEY (edition_year, race_no),
    KEY idx_race_date (race_date),
    CONSTRAINT fk_race_edition FOREIGN KEY (edition_year)
        REFERENCES competition_edition (edition_year)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    -- [REVISION R2] R7 enforced with R2: race category must be offered in that edition
    CONSTRAINT fk_race_edition_category FOREIGN KEY (edition_year, category_id)
        REFERENCES has_category (edition_year, category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE heat (                                   -- weak, owner = race (R8)
    edition_year  SMALLINT     NOT NULL,
    race_no       SMALLINT     NOT NULL,
    heat_no       SMALLINT     NOT NULL,
    start_time    TIME         NULL,
    heat_status   ENUM('Scheduled','Ongoing','Completed','Cancelled')
                  NOT NULL DEFAULT 'Scheduled',
    PRIMARY KEY (edition_year, race_no, heat_no),
    CONSTRAINT fk_heat_race FOREIGN KEY (edition_year, race_no)
        REFERENCES race (edition_year, race_no)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE official (
    official_id     INT           NOT NULL AUTO_INCREMENT,
    first_name      VARCHAR(50)   NOT NULL,
    last_name       VARCHAR(50)   NOT NULL,
    contact_number  VARCHAR(20)  NULL,
    official_role   ENUM('Race Official','Timekeeper','Chief Official') NOT NULL,
    organization    VARCHAR(100)  NULL,
    PRIMARY KEY (official_id)
) ENGINE=InnoDB;

CREATE TABLE supervises (                             -- R9
    official_id   INT       NOT NULL,
    edition_year  SMALLINT  NOT NULL,
    race_no       SMALLINT  NOT NULL,
    heat_no       SMALLINT  NOT NULL,
    PRIMARY KEY (official_id, edition_year, race_no, heat_no),
    CONSTRAINT fk_sup_official FOREIGN KEY (official_id)
        REFERENCES official (official_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_sup_heat FOREIGN KEY (edition_year, race_no, heat_no)
        REFERENCES heat (edition_year, race_no, heat_no)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Phase 3 Stage C removed edition_year here and enforced the heat FK with a
-- trigger. [REVISION R1] edition_year is restored as a NON-key column that is
-- tied to the entry by a composite FK, so MySQL enforces everything natively.
-- The primary key stays exactly as in Phase 3.
CREATE TABLE assigned_to (                            -- R15
    entry_id      INT       NOT NULL,
    race_no       SMALLINT  NOT NULL,
    heat_no       SMALLINT  NOT NULL,
    edition_year  SMALLINT  NOT NULL,
    PRIMARY KEY (entry_id, race_no, heat_no),
    CONSTRAINT fk_at_entry FOREIGN KEY (entry_id, edition_year)
        REFERENCES competition_entry (entry_id, edition_year)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_at_heat FOREIGN KEY (edition_year, race_no, heat_no)
        REFERENCES heat (edition_year, race_no, heat_no)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE records_result (                         -- R10 (aggregate)
    entry_id            INT            NOT NULL,
    race_no             SMALLINT       NOT NULL,
    heat_no             SMALLINT       NOT NULL,
    edition_year        SMALLINT       NOT NULL,      -- [REVISION R1]
    official_id         INT            NULL,       -- [REVISION R6] recording official is not published
    raw_time            DECIMAL(8,3)   NULL,          -- must be NULL for DNS/DNF/DQ
    penalty_seconds     DECIMAL(6,2)   NOT NULL DEFAULT 0,
    `rank`              INT            NULL,          -- RANK is reserved in MySQL 8: always backtick
    result_status       ENUM('Finished','DNS','DNF','DQ') NOT NULL DEFAULT 'Finished',
    recording_timestamp DATETIME       NULL DEFAULT CURRENT_TIMESTAMP,  -- [REVISION R7] NULL for results imported from the website
    PRIMARY KEY (entry_id, race_no, heat_no),
    KEY idx_rr_heat (edition_year, race_no, heat_no),
    CONSTRAINT chk_rr_raw     CHECK (raw_time IS NULL OR raw_time > 0),
    CONSTRAINT chk_rr_penalty CHECK (penalty_seconds >= 0),
    CONSTRAINT chk_rr_rank    CHECK (`rank` IS NULL OR `rank` >= 1),
    CONSTRAINT chk_rr_status  CHECK ((result_status = 'Finished' AND raw_time IS NOT NULL)
                                  OR (result_status <> 'Finished' AND raw_time IS NULL)),
    CONSTRAINT fk_rr_entry FOREIGN KEY (entry_id, edition_year)
        REFERENCES competition_entry (entry_id, edition_year)
        ON UPDATE CASCADE ON DELETE RESTRICT,         -- D1: entry with results cannot be deleted
    CONSTRAINT fk_rr_heat FOREIGN KEY (edition_year, race_no, heat_no)
        REFERENCES heat (edition_year, race_no, heat_no)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rr_official FOREIGN KEY (official_id)
        REFERENCES official (official_id)
        ON UPDATE CASCADE ON DELETE RESTRICT          -- Phase 2 5.4: protect results from official deletion
) ENGINE=InnoDB;

CREATE TABLE result_correction_log (                  -- R13, R14
    correction_id  INT           NOT NULL AUTO_INCREMENT,
    entry_id       INT           NOT NULL,
    race_no        SMALLINT      NOT NULL,
    heat_no        SMALLINT      NOT NULL,
    official_id    INT           NOT NULL,
    old_value      VARCHAR(100)  NOT NULL,
    new_value      VARCHAR(100)  NOT NULL,
    reason         VARCHAR(255)  NOT NULL,
    corrected_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (correction_id),
    CONSTRAINT fk_log_result FOREIGN KEY (entry_id, race_no, heat_no)
        REFERENCES records_result (entry_id, race_no, heat_no)
        ON UPDATE CASCADE ON DELETE RESTRICT,         -- audit trail must survive (Phase 2 5.4 scenario 3)
    CONSTRAINT fk_log_official FOREIGN KEY (official_id)
        REFERENCES official (official_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 4. triggers: disjointness of PAIR_ENTRY / TEAM_ENTRY ------------------
-- (Totality - every entry has exactly one subtype row - cannot be enforced
--  natively; the application inserts entry + subtype in one transaction.)

DELIMITER $$

CREATE TRIGGER trg_pair_not_team BEFORE INSERT ON pair_entry
FOR EACH ROW
BEGIN
    IF EXISTS (SELECT 1 FROM team_entry WHERE entry_id = NEW.entry_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Entry is already a TEAM_ENTRY (disjoint specialization)';
    END IF;
END$$

CREATE TRIGGER trg_team_not_pair BEFORE INSERT ON team_entry
FOR EACH ROW
BEGIN
    IF EXISTS (SELECT 1 FROM pair_entry WHERE entry_id = NEW.entry_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Entry is already a PAIR_ENTRY (disjoint specialization)';
    END IF;
END$$

CREATE TRIGGER trg_race_date_ins BEFORE INSERT ON race
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM competition_edition e
                   WHERE e.edition_year = NEW.edition_year
                     AND NEW.race_date BETWEEN e.start_date AND e.end_date) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Race date must fall within the edition date range (rule 7)';
    END IF;
END$$

CREATE TRIGGER trg_race_date_upd BEFORE UPDATE ON race
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM competition_edition e
                   WHERE e.edition_year = NEW.edition_year
                     AND NEW.race_date BETWEEN e.start_date AND e.end_date) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Race date must fall within the edition date range (rule 7)';
    END IF;
END$$

DELIMITER ;
