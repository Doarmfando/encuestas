import unittest

from app.services.generator_service import GeneratorService


class GeneratorServiceConfigTest(unittest.TestCase):
    def test_generate_uses_json_config_for_dropdown_age(self):
        service = GeneratorService()
        configuracion = {
            "perfiles": [
                {
                    "nombre": "Perfil prueba",
                    "frecuencia": 100,
                    "respuestas": {
                        "Edad": {
                            "tipo": "aleatorio",
                            "opciones": {
                                "32 - 38": 100,
                            },
                        }
                    },
                }
            ],
            "reglas_dependencia": [],
            "tendencias_escalas": [],
        }
        estructura = {
            "paginas": [
                {
                    "numero": 1,
                    "preguntas": [
                        {
                            "texto": "Edad",
                            "tipo": "desplegable",
                            "opciones": ["18 - 24", "25 - 31", "32 - 38", "39 - 45"],
                        }
                    ],
                    "botones": ["Siguiente"],
                }
            ]
        }

        respuesta = service.generate(configuracion, estructura)
        edad = respuesta["paginas"][0]["respuestas"][0]["valor"]

        self.assertEqual(edad, "32 - 38")


if __name__ == "__main__":
    unittest.main()
