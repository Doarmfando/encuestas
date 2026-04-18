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

    def test_generate_supports_conditional_multiselect_patterns_and_cardinality_rules(self):
        service = GeneratorService()
        configuracion = {
            "perfiles": [
                {
                    "nombre": "Perfil trabajador",
                    "frecuencia": 100,
                    "respuestas": {
                        "¿Actualmente trabajas?": {
                            "tipo": "aleatorio",
                            "opciones": {"Si": 100},
                        },
                        "Cantidad de días que el estudiante trabaja en la semana": {
                            "tipo": "seleccion_multiple_condicionada",
                            "patrones": {"5_dias": 100},
                        },
                    },
                }
            ],
            "reglas_dependencia": [
                {
                    "si_pregunta": "Cantidad de días que el estudiante trabaja en la semana",
                    "operador": "cardinalidad_igual",
                    "si_valor": 5,
                    "entonces_pregunta": "Cantidad de días que el estudiante trabaja en la semana",
                    "entonces_forzar": ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"],
                    "entonces_excluir": ["Sabado", "Domingo"],
                }
            ],
            "tendencias_escalas": [],
        }
        estructura = {
            "paginas": [
                {
                    "numero": 1,
                    "preguntas": [
                        {
                            "texto": "¿Actualmente trabajas?",
                            "tipo": "opcion_multiple",
                            "opciones": ["Si", "No"],
                            "obligatoria": True,
                        },
                        {
                            "texto": "Cantidad de días que el estudiante trabaja en la semana",
                            "tipo": "seleccion_multiple",
                            "opciones": ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"],
                            "obligatoria": True,
                        },
                    ],
                    "botones": ["Enviar"],
                }
            ]
        }

        respuesta = service.generate(configuracion, estructura)
        dias = respuesta["paginas"][0]["respuestas"][1]["valor"]

        self.assertEqual(dias, ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"])

    def test_generate_required_multiselect_falls_back_to_one_option_when_empty(self):
        service = GeneratorService()
        configuracion = {
            "perfiles": [
                {
                    "nombre": "Perfil sin dias",
                    "frecuencia": 100,
                    "respuestas": {
                        "Cantidad de días que el estudiante trabaja en la semana": {
                            "tipo": "seleccion_multiple_condicionada",
                            "patrones": {"sin_dias": 100},
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
                            "texto": "Cantidad de días que el estudiante trabaja en la semana",
                            "tipo": "seleccion_multiple",
                            "opciones": ["Lunes", "Martes", "Miercoles"],
                            "obligatoria": True,
                        }
                    ],
                    "botones": ["Enviar"],
                }
            ]
        }

        respuesta = service.generate(configuracion, estructura)
        dias = respuesta["paginas"][0]["respuestas"][0]["valor"]

        self.assertEqual(len(dias), 1)
        self.assertIn(dias[0], ["Lunes", "Martes", "Miercoles"])


if __name__ == "__main__":
    unittest.main()
