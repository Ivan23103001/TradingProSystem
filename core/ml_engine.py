import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os

MODEL_PATH = "ml_trading_model.pkl"

def prepare_features(df):
    """
    Convierte indicadores técnicos en características (features) para el modelo.
    """
    try:
        if df is None or len(df) < 50:
            return pd.DataFrame(), pd.Series(), []
            
        data = df.copy()
        features = ['RSI', 'Stoch_K', 'MACD_Hist', 'EMA_20', 'EMA_50', 'BB_High', 'BB_Low']
        
        # Verificar columnas
        if not all(f in data.columns for f in features):
            return pd.DataFrame(), pd.Series(), []
            
        data['Dist_EMA20'] = (data['Close'] - data['EMA_20']) / data['EMA_20']
        data['Dist_EMA50'] = (data['Close'] - data['EMA_50']) / data['EMA_50']
        data['Return_1d'] = data['Close'].pct_change()
        
        final_features = features + ['Dist_EMA20', 'Dist_EMA50', 'Return_1d']
        data['Target'] = (data['Close'].shift(-5) > data['Close'] * 1.02).astype(int)
        data = data.dropna()
        
        if data.empty:
            return pd.DataFrame(), pd.Series(), []
            
        return data[final_features], data['Target'], final_features
    except Exception:
        return pd.DataFrame(), pd.Series(), []

def train_trading_model(df, n_estimators=100, max_depth=10):
    """
    Entrena un modelo Random Forest simplificado.
    """
    try:
        if len(df) < 100:
            return None, "Datos insuficientes"
            
        X, y, _ = prepare_features(df)
        if len(X) < 50:
            return None, "Datos válidos insuficientes"
            
        model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        model.fit(X, y)
        joblib.dump(model, MODEL_PATH)
        return model, "Entrenamiento exitoso"
    except Exception as e:
        return None, str(e)

def get_ml_prediction(df):
    """
    Versión blindada de predicción ML (Sin accesos por índice riesgosos).
    """
    try:
        if not os.path.exists(MODEL_PATH):
            if len(df) >= 100:
                model, _ = train_trading_model(df)
                if model is None: return 50
            else:
                return 50
                
        model = joblib.load(MODEL_PATH)
        X, _, _ = prepare_features(df)
        
        if X.empty:
            return 50
            
        # Usar la última fila para predecir
        last_row = X.iloc[[-1]]
        probs = model.predict_proba(last_row)[0] # Array de (n_classes,)
        
        # Obtener la probabilidad de la clase '1' de forma segura
        # model.classes_ nos dice qué índice corresponde a qué clase
        classes = model.classes_.tolist()
        if 1 in classes:
            idx_class_1 = classes.index(1)
            # Solo si el índice existe en el array de probabilidades
            if idx_class_1 < len(probs):
                prob = probs[idx_class_1]
                return int(prob * 100)
        
        # Si la clase 1 no está o el índice falla, devolvemos neutral o basado en clase 0
        if 0 in classes and len(probs) > classes.index(0):
            prob_0 = probs[classes.index(0)]
            return int((1 - prob_0) * 100)
            
        return 50
    except Exception:
        return 50
