# Spec Delta

## Purpose

Define el comportamiento observable de la emisión del token de sesión por
`POST /auth/login`: qué claims mínimos debe contener, cómo se deriva y
valida el claim `client`, cómo se firma criptográficamente, cómo se calcula
`expiresIn`, y qué no debe exponerse (secreto, token) en registros.

## ADDED Requirements

### Requirement: Claims mínimos del token
El token emitido por `POST /auth/login` ante credenciales válidas SHALL
incluir, como mínimo, los claims `sub`, `client`, `iat` y `exp`.

#### Scenario: Login válido produce los claims mínimos
- **WHEN** un usuario envía `username`, `password` y `client` válidos a
  `POST /auth/login`
- **THEN** la respuesta es `200` y el `token` emitido, al decodificarse,
  contiene los claims `sub`, `client`, `iat` y `exp` con valores no vacíos

### Requirement: Claim `client` derivado y validado desde la solicitud
El sistema SHALL tomar el claim `client` del campo `client` de la solicitud
de login, SHALL rechazar una solicitud sin un `client` válido, y el valor
reflejado en el token emitido SHALL coincidir exactamente con el enviado.

#### Scenario: Client ausente se rechaza
- **WHEN** se envía `POST /auth/login` con `username` y `password` válidos
  pero sin el campo `client` (o vacío)
- **THEN** la respuesta es `400` y no se emite ningún token

#### Scenario: Client enviado se refleja sin alterar
- **WHEN** se envía `POST /auth/login` con `client` igual a
  `"angular-workshop"` y credenciales válidas
- **THEN** el claim `client` del token decodificado es exactamente
  `"angular-workshop"`

### Requirement: Token firmado criptográficamente
El token emitido SHALL estar firmado de forma que una verificación con la
clave o secreto correctos confirme su integridad, y SHALL dejar de usar
una codificación reversible sin firma (Base64 plano) como mecanismo de
protección.

#### Scenario: Token con firma válida se verifica
- **WHEN** se verifica el token emitido por un login válido usando la
  clave o secreto de verificación configurado para el entorno
- **THEN** la verificación confirma que la firma es válida y que el
  contenido (claims) no fue alterado

#### Scenario: Token alterado falla la verificación
- **WHEN** se modifica cualquier byte del token emitido (payload o firma) y
  se intenta verificar con la clave o secreto configurado
- **THEN** la verificación rechaza el token como inválido

### Requirement: Coherencia entre `expiresIn` y `exp`
El campo `expiresIn` de la respuesta SHALL ser coherente con `exp - iat`
(o `exp - now` al momento de emisión) del token, dentro de una tolerancia
documentada por la configuración del servicio, en vez de un valor
constante desconectado del claim `exp` real.

#### Scenario: expiresIn coincide con la expiración real del token
- **WHEN** un login válido emite un token con claims `iat` y `exp`
- **THEN** `expiresIn` de la respuesta y `exp - iat` difieren, como máximo,
  en la tolerancia documentada para el servicio

### Requirement: Secreto de firma restringido o documentado
Un secreto o clave de firma por defecto incluido en el código o
configuración de ejemplo SHALL aplicarse únicamente en el entorno de
laboratorio y SHALL estar documentado como tal, o bien el sistema SHALL
exigir una clave/secreto configurado explícitamente fuera del
laboratorio.

#### Scenario: Entorno de laboratorio documentado
- **WHEN** se inspecciona la configuración de firma usada en el entorno de
  laboratorio
- **THEN** el valor por defecto usado, si existe, está documentado
  explícitamente como exclusivo de laboratorio

#### Scenario: Entorno fuera de laboratorio sin secreto configurado
- **WHEN** el servicio se ejecuta fuera del laboratorio y no se configuró
  explícitamente un secreto o clave de firma
- **THEN** el servicio no emite tokens firmados con el valor por defecto de
  laboratorio

### Requirement: Sin registro de tokens ni secretos
El sistema SHALL NOT escribir en logs el valor del token emitido ni el
valor del secreto o clave de firma, en ningún nivel de registro usado en
operación normal.

#### Scenario: Login exitoso no registra datos sensibles
- **WHEN** ocurre un login válido que emite un token
- **THEN** ninguna línea de log generada por esa solicitud contiene el
  token completo ni el secreto o clave de firma

### Requirement: Contrato de `POST /auth/login` preservado
Los cambios de firma y claims SHALL preservar la ruta, el método y la
forma de la respuesta ya observada: `200` con `token`, `expiresIn` y
`user` ante credenciales válidas; `400` si falta `username` o `password`;
`401` ante credenciales inválidas; `500` ante un error no esperado.

#### Scenario: Respuesta exitosa conserva su forma
- **WHEN** un login válido se completa
- **THEN** la respuesta `200` incluye `token`, `expiresIn` y `user` con
  `username`, `displayName` y `role`

#### Scenario: Credenciales inválidas conservan su código de estado
- **WHEN** se envía un `username` o `password` que no coincide con ningún
  registro
- **THEN** la respuesta es `401` y no se emite ningún token
