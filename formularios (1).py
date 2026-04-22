import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import time

# Cargar el archivo Excel
df = pd.read_excel(r"E:\webscrolling utp\paginawebgrupopri\excelutp.xlsx")  # Asegúrate de incluir la ruta correcta al archivo
# Opciones de Chrome

for index, row in df.iterrows():
    # Acceder a cada columna por su nombre
    variable1 = row['PREGUNTA1']
    variable2 = row['PREGUNTA2']
    variable3 = row['PREGUNTA3']
    variable4 = row['PREGUNTA4']

    options = Options()
    options.add_argument("--allow-running-insecure-content")  # Permitir contenido inseguro
    options.add_argument("--ignore-certificate-errors")  # Ignorar errores de certificado
    options.headless = False  # Cambiar a True si quieres ejecutar en modo headless
    # Especificando el servicio con la ruta correcta del ChromeDriver
    service = Service(executable_path=r'C:\dchrome\chromedriver_129.0.6668.71.exe')

    # Creando el driver con las opciones
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://forms.office.com/Pages/ResponsePage.aspx?id=NGymxLcrH0WL4bLCakMBWItITGVtFflDm6szMcphPRZUOUNUQ1IySE5IOTNLTEFVOUxIUUozNzFZWC4u')
    print(f"PREGUNTA1: {variable1},PREGUNTA2: {variable2},PREGUNTA3: {variable3},PREGUNTA4: {variable4}")

    try:
        wait = WebDriverWait(driver, 10)
        boton_descargar = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="form-main-content1"]/div/div[3]/div[3]/button')))
        boton_descargar.click()

        time.sleep(3)

        # PREGUNTA 1
        si_option_xpath = f"//input[@name='re2f984b143e94931bd2e2aee8eb576f3' and @aria-posinset='{variable1}']"
        si_option = wait.until(EC.presence_of_element_located((By.XPATH, si_option_xpath)))
        driver.execute_script("arguments[0].click();", si_option)

        # PREGUNTA 2
        si_option_xpath = f"//input[@name='re328a9c48ce54090975ff9fbd49a7659' and @aria-posinset='{variable2}']"
        si_option = wait.until(EC.presence_of_element_located((By.XPATH, si_option_xpath)))
        driver.execute_script("arguments[0].click();", si_option)

        # PREGUNTA 3
        si_option_xpath = f"//input[@name='r778e51eb5cea40169f55d60cbca91d1d' and @aria-posinset='{variable3}']"
        si_option = wait.until(EC.presence_of_element_located((By.XPATH, si_option_xpath)))
        driver.execute_script("arguments[0].click();", si_option)

        # PREGUNTA 4
        si_option_xpath = f"//input[@name='r67f23cb0ef0649718779823bc81b39ca' and @aria-posinset='{variable4}']"
        si_option = wait.until(EC.presence_of_element_located((By.XPATH, si_option_xpath)))
        driver.execute_script("arguments[0].click();", si_option)

        boton_descargar = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="form-main-content1"]/div[3]/div/div[2]/div[2]/div/button')))
        boton_descargar.click()

        print("Clic realizado con éxito.")
        time.sleep(4)

    except TimeoutException:
        print("No se pudo cargar un elemento a tiempo.")
    except NoSuchElementException:
        print("No se encontró uno de los elementos necesarios.")
    except Exception as e:
        print(f"Ocurrió un error: {str(e)}")
    finally:
        time.sleep(2)  # Pausa entre cada envío
driver.quit()
