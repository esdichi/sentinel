create table sentinel_cab (
codigo int unsigned primary key,
aviso varchar(355))
engine = InnoDB;

create table sentinel_log (
codigo int unsigned primary key auto_increment,
tipo int unsigned,
empleado int unsigned,
tienda int unsigned,
fecha date,
hora time,
notificado boolean default FALSE,
constraint FOREIGN KEY(tipo) REFERENCES sentinel_cab(codigo) ON DELETE CASCADE ON UPDATE CASCADE)
engine = INNODB;

create table sentinel_obs (
codigo int unsigned primary key,
observaciones longtext)
engine = InnoDB;

create table sentinel_dat (
codigo int unsigned,
numero int unsigned,
valor varchar(355),
constraint primary key(codigo,numero))
engine = InnoDB;

create table sentinel_mail (
codigo int unsigned,
numero int unsigned,
mail varchar(255),
constraint foreign key(codigo) REFERENCES sentinel_cab(codigo) ON DELETE CASCADE ON UPDATE CASCADE)
engine = INNODB;
