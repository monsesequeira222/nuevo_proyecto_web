from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, render_template, request, make_response
from io import StringIO
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend for matplotlib
import matplotlib.pyplot as plt
import threading

app = Flask(__name__)

# Global variable for storing the results DataFrame
global_results_df = pd.DataFrame()

# Function to calculate the mode safely
def safe_mode(series):
    try:
        if series.empty:
            return None
        return ', '.join(series.mode().astype(str))
    except Exception as e:
        print(f"Error calculating mode: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    global global_results_df  # Declare the global variable to store the results DataFrame
    resultados = None
    error_message = None
    current_date = datetime.now()
    top_products = None

    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename != '':
            try:
                dataframe = pd.read_csv(StringIO(uploaded_file.read().decode('utf-8')))
                
                required_columns = {'Cliente', 'Fecha', 'Producto', 'Precio'}
                if not required_columns.issubset(dataframe.columns):
                    error_message = "Las columnas requeridas no están en el archivo CSV."
                else:
                    dataframe['Fecha'] = pd.to_datetime(dataframe['Fecha'])
                    dataframe.sort_values(by=['Cliente', 'Fecha'], inplace=True)
                    
                    dataframe['Diferencia'] = dataframe.groupby('Cliente')['Fecha'].diff().dt.days.fillna(0)
                    stats_df = dataframe.groupby('Cliente').agg({
                        'Fecha': 'max',
                        'Producto': safe_mode,
                        'Precio': ['count', 'sum'],
                        'Diferencia': 'mean'
                    }).reset_index()

                    # Rename columns
                    stats_df.columns = ['Cliente', 'Última_Compra', 'Producto_Frecuente', 'Total_Compras', 'Total_Gastado', 'Frecuencia_Promedio']

                    # Calculate 'Próxima_Compra_Estimada' and 'Días_Desde_Próxima_Compra'
                    stats_df['Próxima_Compra_Estimada'] = stats_df.apply(
                        lambda row: row['Última_Compra'] + timedelta(days=int(row['Frecuencia_Promedio'])), axis=1
                    )
                    stats_df['Días_Desde_Próxima_Compra'] = stats_df.apply(
                        lambda row: (current_date - row['Próxima_Compra_Estimada']).days if row['Próxima_Compra_Estimada'] < current_date else 0, axis=1
                    )

                    # Format dates for display
                    stats_df['Última_Compra'] = stats_df['Última_Compra'].dt.strftime('%m/%d/%Y')
                    stats_df['Próxima_Compra_Estimada'] = stats_df['Próxima_Compra_Estimada'].dt.strftime('%m/%d/%Y')

                    # Replace NaN with 'No disponible'
                    stats_df.fillna('No disponible', inplace=True)

                    # Store the results in global_results_df for CSV download
                    global_results_df = stats_df.copy()

                    resultados = stats_df.to_dict('records')

                    # Analysis of top-selling products
                    sales_df = dataframe.groupby('Producto').agg({'Precio': 'sum'}).sort_values('Precio', ascending=False).reset_index()
                    top_products = sales_df.head(5).to_dict('records')

                    # Generate and save the sales chart in a separate thread
                    threading.Thread(target=generate_chart, args=(dataframe,)).start()

            except Exception as e:
                error_message = str(e)

    return render_template(
        'index.html', 
        resultados=resultados, 
        top_products=top_products, 
        error=error_message, 
        current_date=current_date.strftime('%m/%d/%Y')
    )

# Function to generate and save the sales chart
def generate_chart(dataframe):
    try:
        # Group by month and sum the sales
        monthly_sales = dataframe.groupby(dataframe['Fecha'].dt.strftime('%Y-%m'))['Precio'].sum()

        # Convert index from string to date format
        monthly_sales.index = pd.to_datetime(monthly_sales.index)

        # Sort by date
        monthly_sales.sort_index(inplace=True)

        # Create a bar chart
        plt.figure(figsize=(10, 6))
        monthly_sales.plot(kind='bar', color='skyblue')
        plt.xlabel('Mes')
        plt.ylabel('Ventas Totales')
        plt.title('Ventas por Mes')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('monthly_sales_chart.png', format='png')
    except Exception as e:
        print(f"Error generating chart: {e}")

@app.route('/download/csv')
def download_csv():
    global global_results_df  # Reference the global variable for results DataFrame
    if not global_results_df.empty:
        # Convert the DataFrame to CSV
        csv_data = global_results_df.to_csv(index=False)
        response = make_response(csv_data)
        response.headers['Content-Disposition'] = 'attachment; filename=results_data.csv'
        response.mimetype = 'text/csv'
        return response
    else:
        return "No data available to download.", 404

if __name__ == '__main__':
    app.run(debug=True)







