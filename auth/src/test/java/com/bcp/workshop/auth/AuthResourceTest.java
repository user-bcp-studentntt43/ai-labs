package com.bcp.workshop.auth;

import io.quarkus.test.junit.QuarkusTest;
import io.restassured.response.Response;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.is;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.notNullValue;
import static org.hamcrest.Matchers.nullValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@QuarkusTest
class AuthResourceTest {
    private static final String VALID_LOGIN =
            "{\"username\":\"student\",\"password\":\"Workshop123!\",\"client\":\"angular-workshop\"}";

    private static Response login(String body) {
        return given().contentType("application/json").body(body).when().post("/auth/login");
    }

    @Test
    void logsInWithWorkshopUser() {
        given()
                .contentType("application/json")
                .body("{\"username\":\"student\",\"password\":\"Workshop123!\",\"client\":\"angular-workshop\"}")
                .when().post("/auth/login")
                .then()
                .statusCode(200)
                .body("user.username", is("student"))
                .body("token", notNullValue());
    }

    // Caracteriza el token legado (Base64 sin firma) que reemplaza la tarea 4.1; spec "Token firmado".
    @Test
    void issuesUnsignedBase64TokenWithUsernameRoleExpiryAndSecret() {
        long before = Instant.now().getEpochSecond();
        String token = login(VALID_LOGIN).then().statusCode(200).extract().path("token");
        long after = Instant.now().getEpochSecond();

        String[] parts = new String(Base64.getDecoder().decode(token), StandardCharsets.UTF_8).split("\\|", -1);

        assertEquals(4, parts.length);
        assertEquals("student", parts[0]);
        assertEquals("STUDENT", parts[1]);
        long expiry = Long.parseLong(parts[2]);
        assertTrue(expiry >= before + 3600 && expiry <= after + 3600);
        assertFalse(parts[3].isBlank());
    }

    // Caracteriza el valor constante que la tarea 4.2 deriva de exp - iat; spec "Coherencia entre expiresIn y exp".
    @Test
    void reportsConstantExpiresInOf3600() {
        login(VALID_LOGIN).then().statusCode(200).body("expiresIn", is(3600));
    }

    // Caracteriza que hoy `client` no se valida; la tarea 2.1 lo cambia a 400. Spec "Claim client".
    @Test
    void acceptsLoginWithoutClient() {
        login("{\"username\":\"student\",\"password\":\"Workshop123!\"}")
                .then().statusCode(200).body("token", notNullValue());
    }

    // Igual que la anterior, para `client` vacío.
    @Test
    void acceptsLoginWithBlankClient() {
        login("{\"username\":\"student\",\"password\":\"Workshop123!\",\"client\":\"\"}")
                .then().statusCode(200).body("token", notNullValue());
    }

    // Protege el 400 de username faltante o en blanco; spec "Contrato de POST /auth/login preservado".
    @Test
    void rejectsMissingOrBlankUsernameWith400() {
        login("{\"password\":\"Workshop123!\",\"client\":\"angular-workshop\"}")
                .then().statusCode(400).body("message", is("Username is required")).body("token", nullValue());
        login("{\"username\":\"   \",\"password\":\"Workshop123!\",\"client\":\"angular-workshop\"}")
                .then().statusCode(400).body("message", is("Username is required")).body("token", nullValue());
    }

    // Protege el 400 de password faltante o en blanco; spec "Contrato de POST /auth/login preservado".
    @Test
    void rejectsMissingOrBlankPasswordWith400() {
        login("{\"username\":\"student\",\"client\":\"angular-workshop\"}")
                .then().statusCode(400).body("message", is("Password is required")).body("token", nullValue());
        login("{\"username\":\"student\",\"password\":\"   \",\"client\":\"angular-workshop\"}")
                .then().statusCode(400).body("message", is("Password is required")).body("token", nullValue());
    }

    // Protege el 401 sin token y su mensaje actual con el username; spec "Credenciales inválidas conservan su código".
    @Test
    void rejectsInvalidCredentialsWith401AndNoToken() {
        login("{\"username\":\"student\",\"password\":\"wrong\",\"client\":\"angular-workshop\"}")
                .then().statusCode(401).body("message", is("Invalid user student or password")).body("token", nullValue());
        login("{\"username\":\"nobody\",\"password\":\"wrong\",\"client\":\"angular-workshop\"}")
                .then().statusCode(401).body("message", is("Invalid user nobody or password")).body("token", nullValue());
    }

    // Protege la forma completa del 200, incluido `debug`; spec "Respuesta exitosa conserva su forma".
    @Test
    void keepsFullSuccessResponseShape() {
        login(VALID_LOGIN)
                .then()
                .statusCode(200)
                .body("keySet()", containsInAnyOrder("token", "expiresIn", "user", "debug"))
                .body("user.keySet()", containsInAnyOrder("username", "displayName", "role"))
                .body("user.username", is("student"))
                .body("user.displayName", is("Workshop Student"))
                .body("user.role", is("STUDENT"))
                .body("debug", is("authenticated-with-legacy-flow"));
    }
}
