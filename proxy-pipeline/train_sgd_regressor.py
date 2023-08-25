import os
import pickle

from absl import flags
from absl import app

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error as mse
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.preprocessing import OneHotEncoder, LabelEncoder

# Define parameters for the training/handling of the data and model
flags.DEFINE_string('data_path', './data', 'Path to the data')
flags.DEFINE_string('model_path', './models', 'Path to the model')
flags.DEFINE_integer('seed', 123, 'Seed for the random number generator')
flags.DEFINE_float('train_size', 0.8, 'the split between train and test dataset')
flags.DEFINE_enum('preprocess', 'normalize', ['normalize', 'standardize'], 'Preprocessing method')
flags.DEFINE_enum('encode', 'one_hot', ['one_hot', 'label'], 'Encoding method')
flags.DEFINE_bool('visualize', False, 'enable visualization of the data')
flags.DEFINE_bool('train', False, 'enable training of the model')

# Hyperparameters for the model
flags.DEFINE_string('loss', 'squared_error', 'The loss function to be used')
flags.DEFINE_enum('penalty', 'l2', ['l2', 'l1', 'elasticnet'], 'The penalty to be used')
flags.DEFINE_float('alpha', 0.0001, 'The regularization term')
flags.DEFINE_float('l1_ratio', 0.15, 'The Elastic Net mixing parameter')
flags.DEFINE_bool('fit_intercept', True, 'Whether to calculate the intercept for this model')
flags.DEFINE_integer('max_iter', 1000, 'The maximum number of passes over the training data')
flags.DEFINE_float('tol', 1e-3, 'The stopping criterion')
flags.DEFINE_bool('shuffle', True, 'Whether or not the training data should be shuffled after each epoch')
flags.DEFINE_integer('verbose', 0, 'The verbosity level')
flags.DEFINE_float('epsilon', 0.1, 'Epsilon in the epsilon-insensitive loss functions')
flags.DEFINE_integer('random_state', None, 'Used for shuffling the data, when shuffle is set to True')
flags.DEFINE_string('learning_rate', 'invscaling', 'The learning rate schedule')
flags.DEFINE_float('eta0', 0.01, 'The initial learning rate for the invscaling learning rate')
flags.DEFINE_float('power_t', 0.25, 'The exponent for inverse scaling learning rate')
flags.DEFINE_bool('early_stopping', False, 'Whether to use early stopping to terminate training when validation score is not improving')
flags.DEFINE_float('validation_fraction', 0.1, 'The proportion of training data to set aside as validation set for early stopping')
flags.DEFINE_integer('n_iter_no_change', 5, 'The number of iterations with no improvement to wait before early stopping')
flags.DEFINE_bool('warm_start', False, 'When set to True, reuse the solution of the previous call to fit as initialization, otherwise, just erase the previous solution')
flags.DEFINE_integer('average', False, 'When set to True, computes the averaged SGD weights and stores the result in the coef_ attribute. If set to an int greater than 1, averaging will begin once the total number of samples seen reaches average. So average=10 will begin averaging after seeing 10 samples')

FLAGS = flags.FLAGS

def preprocess_data(actions, observations, exp_path):
    # Categorical features
    categorical_cols = list(set(actions.columns) - set(actions._get_numeric_data().columns))
    categorical_actions = actions[categorical_cols]
    
    # Numerical features
    numerical_actions = actions._get_numeric_data()
    
    encoder_path = os.path.join(exp_path, 'encoder')
    if not os.path.exists(encoder_path):
        os.makedirs(encoder_path)

    # Encode categorical features
    if FLAGS.encode == 'one_hot':
        # One-hot encode categorical features
        enc = OneHotEncoder(handle_unknown='ignore')
        enc.fit(categorical_actions)
        # Save the encoder
        path = os.path.join(encoder_path, 'one_hot_encoder.joblib')
        pickle.dump(enc, open(path, 'wb'))
        # Transform the categorical features
        dummy_col_names = pd.get_dummies(categorical_actions).columns
        categorical_actions = pd.DataFrame(enc.transform(categorical_actions).toarray(), columns=dummy_col_names)
    elif FLAGS.encode == 'label':
        dummy_actions = pd.DataFrame()
        for categorical_col in categorical_cols:
            # Label encode categorical features
            enc = LabelEncoder()
            enc.fit(categorical_actions[categorical_col])
            # Save the encoder
            path = os.path.join(encoder_path, 'label_encoder_{}.joblib'.format(categorical_col))
            pickle.dump(enc, open(path, 'wb'))
            # Transform the categorical features
            dummy_actions[categorical_col] = enc.transform(categorical_actions[categorical_col])
        categorical_actions = pd.DataFrame(dummy_actions, columns=categorical_cols)
    else:
        raise ValueError('Encoding method not supported')

    preprocess_data_path = os.path.join(exp_path, 'preprocess_data')
    if not os.path.exists(preprocess_data_path):
        os.makedirs(preprocess_data_path)

    # Normalize numerical features
    if FLAGS.preprocess == 'normalize':
        # Normalize numerical features for actions
        normalize_feature_transformer = MinMaxScaler(feature_range=(0, 1))
        normalized_numerical_features = normalize_feature_transformer.fit_transform(numerical_actions)
        numerical_actions = pd.DataFrame(normalized_numerical_features, columns=[numerical_actions.columns])
        # Save the scaler
        path = os.path.join(preprocess_data_path, 'normalize_feature_transformer_actions.joblib')
        pickle.dump(normalize_feature_transformer, open(path, 'wb'))
        
        # Normalize numerical features for observations
        normalize_feature_transformer = MinMaxScaler(feature_range=(0, 1))
        normalized_numerical_features = normalize_feature_transformer.fit_transform(observations)
        observations = pd.DataFrame(normalized_numerical_features, columns=[observations.columns])
        # Save the scaler
        path = os.path.join(preprocess_data_path, 'normalize_feature_transformer_observations.joblib')
        pickle.dump(normalize_feature_transformer, open(path, 'wb'))
    elif FLAGS.preprocess == 'standardize':
        # Standardize numerical features for actions
        standardize_feature_transformer = StandardScaler()
        standardized_numerical_features = standardize_feature_transformer.fit_transform(numerical_actions)
        numerical_actions = pd.DataFrame(standardized_numerical_features, columns=[numerical_actions.columns])
        # Save the scaler
        path = os.path.join(preprocess_data_path, 'standardize_feature_transformer_actions.joblib')
        pickle.dump(standardize_feature_transformer, open(path, 'wb'))
        
        # Standardize numerical features for observations
        standardize_feature_transformer = StandardScaler()
        standardized_numerical_features = standardize_feature_transformer.fit_transform(observations)
        observations = pd.DataFrame(standardized_numerical_features, columns=[observations.columns])
        # Save the scaler
        path = os.path.join(preprocess_data_path, 'standardize_feature_transformer_observations.joblib')
        pickle.dump(standardize_feature_transformer, open(path, 'wb'))
    else:
        raise ValueError('Preprocessing method not supported')

    # Concatenate numerical and categorical features
    actions = pd.concat([numerical_actions, categorical_actions], axis = 1).to_numpy()
    observations = observations.to_numpy()

    return actions, observations


def visualize_data(data, exp_path):
    visualize_path = os.path.join(exp_path, 'visualize')
    if not os.path.exists(visualize_path):
        os.makedirs(visualize_path)

    fig, ax = plt.subplots(data.shape[1], 2)
    
    lambda_values = []
    for i in range(data.shape[1]):
        sns.distplot(data, hist=True, kde=True, kde_kws={'shade': True, 'linewidth': 2},
                 label='Non-Normal', color='green', ax=ax[i,0])
    
        fitted_data, fitted_lambda = stats.boxcox(data.iloc[:,i])
        lambda_values.append(fitted_lambda)

        sns.distplot(fitted_data, hist=True, kde=True, kde_kws={'shade': True, 'linewidth': 2},
                 label='Non-Normal', color='green', ax=ax[i,1])
    

    f = open(os.path.join(visualize_path, 'data_visualization.txt'), 'w')

    for i in range(len(lambda_values)):
        print('Lambda value used for Transformation in {} Sample {}'.format(list(data.columns)[i], lambda_values[i]))
        f.write('Lambda value used for Transformation in {} Sample {}\n'.format(list(data.columns)[i], lambda_values[i]))

    f.close()

    plt.legend(loc='upper right')
    fig.set_figheight(6)
    fig.set_figwidth(15)
    # Save the figure
    fig.savefig(os.path.join(visualize_path, 'data_visualization.png'))
    # Show the figure autoclose after 5 seconds
    plt.show(block=False)
    plt.pause(5)
    plt.close()


def main(_):
    # Constraints for the hyperparameters
    if FLAGS.precompute != 'auto':
        FLAGS.precompute = bool(FLAGS.precompute)
    
    # Define the experiment folder to save the model
    exp_name = 'sgd_regressor'
    exp_path = os.path.join(FLAGS.model_path, exp_name)
    if not os.path.exists(exp_path):
        os.makedirs(exp_path)

    # Load the data
    actions_path = os.path.join(FLAGS.data_path, 'actions_feasible.csv')
    observations_path = os.path.join(FLAGS.data_path, 'observations_feasible.csv')

    actions = pd.read_csv(actions_path)
    observations = pd.read_csv(observations_path)
    observations = observations.drop(['observation-2', 'observation-3', 'observation-4'], axis = 1)

    X, y = preprocess_data(actions, observations, exp_path)

    # Visualize the data
    if FLAGS.visualize:
        visualize_data(observations, exp_path)

    # Train the model
    if FLAGS.train:
        print('------Training the model------')
        # Split the data into train and test
        X_train, X_test, y_train, y_test = train_test_split(X, y, train_size=FLAGS.train_size, random_state=FLAGS.seed)

        # Define the model
        reg = SGDRegressor(loss=FLAGS.loss, penalty=FLAGS.penalty, alpha=FLAGS.alpha, l1_ratio=FLAGS.l1_ratio, fit_intercept=FLAGS.fit_intercept, max_iter=FLAGS.max_iter, tol=FLAGS.tol, shuffle=FLAGS.shuffle, verbose=FLAGS.verbose, epsilon=FLAGS.epsilon, random_state=FLAGS.random_state, learning_rate=FLAGS.learning_rate, eta0=FLAGS.eta0, power_t=FLAGS.power_t, early_stopping=FLAGS.early_stopping, validation_fraction=FLAGS.validation_fraction, n_iter_no_change=FLAGS.n_iter_no_change, warm_start=FLAGS.warm_start, average=FLAGS.average)
        
        # Train the model
        reg.fit(X_train, y_train)

        # Evaluate the model for train dataset
        y_pred = reg.predict(X_train)
        mse_train = mse(y_train, y_pred)
        print('MSE on train set: {}'.format(mse_train))

        # Evaluate the model for test dataset
        y_pred = reg.predict(X_test)
        mse_test = mse(y_test, y_pred)
        print('MSE on test set: {}'.format(mse_test))

        # Save the model
        path = os.path.join(exp_path, 'model.joblib')
        pickle.dump(reg, open(path, 'wb'))

        FLAGS.append_flags_into_file(os.path.join(exp_path, 'flags.txt'))

        loaded_rf = pickle.load(open(path, 'rb'))
        y_pred = loaded_rf.predict(X_test)
        mse_test_load = mse(y_test, y_pred)

        # Check if the model is saved correctly
        if mse_test == mse_test_load:
            print('Model saved successfully at {}'.format(path))
        else:
            raise Exception('Model is not saved correctly')


if __name__ == '__main__':
    app.run(main)