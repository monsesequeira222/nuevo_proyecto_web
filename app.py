import os
from flask import Flask, render_template, request, send_file, make_response, abort, jsonify, redirect, url_for, current_app
from datetime import datetime, timedelta
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Usar un backend no GUI para matplotlib
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from io import BytesIO
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)

# Variable global para almacenar los datos de ventas mensuales
monthly_sales_data = None

# Funciones auxiliares

def safe_mode(series):
    """Calcula la moda de una serie, manejando excepciones y series vacías."""
    try:
        return ', '.join(series.mode().astype(str)) if not series.empty else None
    except Exception as e:
        print(f"Error calculando la moda: {e}")
        return None

def most_frequent(series):
    """Calcula el ítem más frecuente en una serie."""
    try:
        return series.value_counts().idxmax() if not series.empty else None
    except Exception as e:
        print(f"Error calculando el ítem más frecuente: {e}")
        return None

def process_uploaded_file(uploaded_file):
    """Procesa el archivo CSV enviado por el usuario."""
    global monthly_sales_data  # Accede a la variable global

    resultados = None
    top_clients = None
    error_message = None
    top_products = []
    current_date = datetime.now()
    
    if uploaded_file and uploaded_file.filename != '':
        try:
            dataframe = pd.read_csv(BytesIO(uploaded_file.read()), encoding='utf-8')
            required_columns = {'Cliente', 'Fecha', 'Producto', 'Precio'}
            if not required_columns.issubset(dataframe.columns):
                error_message = "Las columnas requeridas no están en el archivo CSV."
            else:
                dataframe['Total_Gastado'] = dataframe['Precio']
                dataframe['Fecha'] = pd.to_datetime(dataframe['Fecha'], errors='coerce')
                dataframe.dropna(subset=['Fecha'], inplace=True)
                dataframe['Mes'] = dataframe['Fecha'].dt.to_period('M').dt.strftime('%Y-%m')
                dataframe.sort_values(by=['Cliente', 'Fecha'], inplace=True)
                dataframe['Diferencia'] = dataframe.groupby('Cliente')['Fecha'].diff().dt.days.fillna(0)
                
                stats_df = dataframe.groupby('Cliente').agg({
                    'Fecha': 'max',
                    'Producto': most_frequent,
                    'Precio': ['count', 'sum'],
                    'Diferencia': 'mean'
                }).reset_index()
                stats_df.columns = ['Cliente', 'Última_Compra', 'Producto_Frecuente', 'Total_Compras', 'Total_Gastado', 'Frecuencia_Promedio']
                stats_df['Próxima_Compra_Estimada'] = stats_df.apply(
                    lambda row: row['Última_Compra'] + timedelta(days=int(row['Frecuencia_Promedio'])), axis=1
                )
                stats_df['Días_Desde_Próxima_Compra'] = stats_df.apply(
                    lambda row: (current_date - row['Próxima_Compra_Estimada']).days if row['Próxima_Compra_Estimada'] < current_date else 0, axis=1
                )
                stats_df['Última_Compra'] = stats_df['Última_Compra'].dt.strftime('%m/%d/%Y')
                stats_df['Próxima_Compra_Estimada'] = stats_df['Próxima_Compra_Estimada'].dt.strftime('%m/%d/%Y')
                stats_df.fillna('No disponible', inplace=True)
                resultados = stats_df.to_dict('records')
                
                # Obtener los 5 clientes principales basados en el total de compras
                top_clients_df = stats_df.nlargest(5, 'Total_Compras')
                top_clients = top_clients_df.to_dict('records')
                
                # Obtener los 5 productos principales
                sales_df = dataframe.groupby('Producto').agg({'Precio': 'sum'}).sort_values('Precio', ascending=False).reset_index()
                top_products = sales_df.head(5).to_dict('records')
                
                # Generación del gráfico de ventas mensuales
                monthly_sales = dataframe.groupby('Mes').agg({'Precio': 'sum'}).reset_index()
                monthly_sales_data = {
                    "months": list(monthly_sales['Mes']),
                    "sales": list(monthly_sales['Precio'])
                }
                
        except Exception as e:
            error_message = str(e)
    
    return resultados, top_clients, top_products, error_message

# Rutas de la aplicación...

@app.route('/')
def home():
    """Ruta para mostrar la página de inicio."""
    return render_template('index.html')

@app.route('/registro')
def registro():
    """Ruta para mostrar la página de registro."""
    return render_template('registro.html')

@app.route('/procesar_registro', methods=['POST'])
def procesar_registro():
    """Procesa los datos de registro del usuario."""
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    # Aquí agregarías la lógica para guardar los datos en la base de datos
    return redirect(url_for('home'))  # Redirigir al home tras registrarse

@app.route('/login')
def login():
    """Ruta para mostrar la página de inicio de sesión."""
    return render_template('login.html')

@app.route('/procesar_login', methods=['POST'])
def procesar_login():
    """Procesa los datos de inicio de sesión del usuario."""
    username = request.form['username']
    password = request.form['password']
    # Verificar credenciales aquí
    return redirect(url_for('home'))  # Redirigir a la página principal si el login es correcto

@app.route('/SubirArchivo.html', methods=['GET', 'POST'])
def subir_archivo():
    """Ruta para mostrar la página de subir archivo y procesar datos."""
    if request.method == 'POST':
        resultados, top_clients, top_products, error_message = process_uploaded_file(request.files.get('file'))
        if error_message:
            return render_template('SubirArchivo.html', error=error_message)
        else:
            return render_template(
                'Resultados.html',
                resultados=resultados,
                top_clients=top_clients,
                top_products=top_products,
                sales_data=monthly_sales_data  # Pasar los datos de ventas mensuales
            )
    else:
        return render_template('SubirArchivo.html')

@app.route('/download/csv', methods=['POST'])
def download_csv():
    """Ruta para descargar los resultados en formato CSV."""
    resultados, _, _, error_message = process_uploaded_file(request.files.get('file'))
    if resultados:
        df = pd.DataFrame(resultados)
        csv_data = df.to_csv(index=False)
        response = make_response(csv_data)
        response.headers['Content-Disposition'] = 'attachment; filename=results_data.csv'
        response.mimetype = 'text/csv'
        return response
    else:
        abort(404)

@app.route('/download_template')
def download_template():
    """Ruta para descargar una plantilla Excel desde el directorio 'static'."""
    try:
        template_path = os.path.join(current_app.root_path, 'static', 'template.csv')
        return send_file(template_path, as_attachment=True)
    except Exception as e:
        print(f"Error al descargar la plantilla: {e}")
        abort(404)

@app.route('/get_sales_data')
def get_sales_data():
    try:
        global monthly_sales_data  # Accede a la variable global
        if monthly_sales_data:
            return jsonify(monthly_sales_data)
        else:
            return jsonify({"error": "No hay datos de ventas mensuales disponibles"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clientes.html', methods=['GET', 'POST'])
def clientes():
    """Ruta para mostrar la página de clientes con datos dinámicos."""
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            resultados, top_clients, top_products, error_message = process_uploaded_file(file)
            if error_message:
                return render_template('clientes.html', error=error_message)
            else:
                return render_template(
                    'clientes.html',
                    resultados=resultados,
                    top_clients=top_clients,
                    top_products=top_products,
                    sales_data=monthly_sales_data  # Pasar los datos de ventas mensuales
                )
        else:
            return render_template('clientes.html', error="No se ha subido ningún archivo.")
    else:
        return render_template('clientes.html')

@app.route('/analisis/<tipo>', methods=['GET'])
def analisis(tipo):
    """Ruta para realizar análisis dinámico basado en el tipo."""
    try:
        if tipo == 'clientes':
            resultados = [
                {"Cliente": "Cliente1", "Total_Compras": 5, "Total_Gastado": 500},
                {"Cliente": "Cliente2", "Total_Compras": 3, "Total_Gastado": 300}
            ]
        elif tipo == 'productos':
            resultados = [
                {"Producto": "Producto1", "Total_Ventas": 100, "Total_Ganancias": 1000},
                {"Producto": "Producto2", "Total_Ventas": 50, "Total_Ganancias": 500}
            ]
        elif tipo == 'vendedores':
            resultados = [
                {"Vendedor": "Vendedor1", "Total_Ventas": 200, "Total_Comisiones": 2000},
                {"Vendedor": "Vendedor2", "Total_Ventas": 150, "Total_Comisiones": 1500}
            ]
        elif tipo == 'dashboard':
            resultados = {
                "months": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"],
                "sales": [1000, 1500, 2000, 1800, 2200]
            }
        else:
            return jsonify({"error": "Tipo de análisis no válido"}), 400
        
        return jsonify({"resultados": resultados})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/data')  # Nueva ruta para manejar solicitudes de datos del gráfico
def get_chart_data():
    try:
        # Aquí es donde deberías calcular los datos de ventas mensuales en tiempo real
        # Puedes hacerlo consultando tu base de datos o realizando cualquier otro cálculo necesario
        # Por ahora, simplemente devolveré un conjunto de datos de ejemplo para demostración
        example_data = {
            "months": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"],
            "sales": [1000, 1500, 2000, 1800, 2200]
        }
        return jsonify(example_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(error):
    """Manejador de errores para la página no encontrada."""
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)














