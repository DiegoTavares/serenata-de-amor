
# coding: utf-8

# # Anomalies in meal prices
# 
# In the Chamber of Deputies' CEAP, there is a list of 1,000's of meal expenses made by congresspeople. The law says that the congressperson cannot pay for any other, even being her advisor or SO. We want to work on this analysis to find possibly illegal and immoral expenses. They may have happened when the politician spent more than needed (e.g. the whole menu costs X but the bill was 2X) or too much in an specific period of time. In the end, we also want to alert about too expensive reibursements, even with an explanation behind of it.
# 
# Note: remember to correct prices with an inflation index (e.g. IPCA).

# In[1]:

get_ipython().magic('matplotlib inline')
import matplotlib.pyplot as plt
import seaborn as sns
sns.set(color_codes=True)

plt.rcParams['figure.figsize'] = (20, 10)


# In[2]:

import numpy as np
import pandas as pd

dataset = pd.read_csv('../data/2016-11-19-reimbursements.xz',
                      dtype={'applicant_id': np.str,
                             'cnpj_cpf': np.str,
                             'congressperson_id': np.str,
                             'subquota_number': np.str},
                      low_memory=False)
dataset = dataset[dataset['congressperson_id'].notnull()]
dataset['issue_date'] = pd.to_datetime(dataset['issue_date'], errors='coerce')
dataset['issue_date_day'] = dataset['issue_date'].apply(lambda date: date.day)
dataset['issue_date_month'] = dataset['issue_date'].apply(lambda date: date.month)
dataset['issue_date_year'] = dataset['issue_date'].apply(lambda date: date.year)
dataset['issue_date_weekday'] = dataset['issue_date'].apply(lambda date: date.weekday())
dataset['issue_date_week'] = dataset['issue_date'].apply(lambda date: date.week)


# In[3]:

is_in_brazil = '(-73.992222 < longitude < -34.7916667) & (-33.742222 < latitude < 5.2722222)'
companies = pd.read_csv('../data/2016-09-03-companies.xz',
                        dtype={'cnpj': np.str},
                        low_memory=False)
companies = companies.query(is_in_brazil)
companies['cnpj'] = companies['cnpj'].str.replace(r'\D', '')
dataset = pd.merge(dataset, companies,
                   how='left',
                   left_on='cnpj_cpf',
                   right_on='cnpj',
                   suffixes=('', '_company'))


# In[4]:

dataset =     dataset.query('subquota_description == "Congressperson meal"')
companies =     companies[companies['cnpj'].isin(dataset.loc[dataset['cnpj'].notnull(),
                                                 'cnpj'])]


# In[5]:

dataset['total_net_value'].describe()


# In[6]:

dataset['total_net_value'].median()


# In[7]:

bottom_99 = dataset['total_net_value'].quantile(0.99)
bottom_99


# In[8]:

dataset[dataset['total_net_value'] < bottom_99].shape


# In[9]:

sns.distplot(dataset.loc[dataset['total_net_value'] < bottom_99, 'total_net_value'],
             bins=30,
             kde=False)


# In[10]:

bottom_99_dataset = dataset.query('total_net_value > {}'.format(bottom_99))
ranking = bottom_99_dataset.groupby('state_company')['total_net_value']     .median().sort_values(ascending=False)

sns.boxplot(x='state_company',
            y='total_net_value',
            data=bottom_99_dataset,
            order=ranking.index)


# In[11]:

bottom_99_dataset.query('state_company == "CE"').shape


# In[12]:

dataset.query('state_company == "CE"').shape


# In[13]:

bottom_99_dataset['state_company'].isnull().sum()


# In[14]:

bottom_99_dataset.query('state_company == "CE"')     .sort_values('total_net_value', ascending=False)


# ## Using Yelp to improve prices information

# In[15]:

yelp = pd.read_csv('../data/2016-11-29-yelp-companies.xz',
                   low_memory=False)
yelp.head()


# We have data for just 8.6% of the companies which received from the "Congressperson meal" subquota.

# In[16]:

yelp['price'].notnull().sum()


# In[17]:

companies.shape


# In[18]:

yelp['price'].isnull().sum()


# In[19]:

yelp['price.int'] = yelp['price'].str.len()
states_with_records =     yelp[yelp['price'].notnull()].groupby('location.state')['location.state'].count() > 10
states_with_records = states_with_records[states_with_records].index


# In[20]:

yelp_just_significant_states =     yelp[yelp['price'].notnull() &
         yelp['location.state'].isin(states_with_records)]
yelp_just_significant_states['location.state'].value_counts()


# ## Predict prices

# In[21]:

bottom_99_dataset.iloc[0, :57]


# **DummyRegressor with mean strategy as a baseline**

# In[22]:

from sklearn.dummy import DummyRegressor
from sklearn.model_selection import train_test_split

X = bottom_99_dataset[['year']]
y = bottom_99_dataset['total_net_value']
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=0)

model = DummyRegressor(strategy='mean')
model.fit(X_train, y_train)
model.score(X_test, y_test)


# In[23]:

from sklearn.preprocessing import LabelEncoder

le_state = LabelEncoder()
le_city = LabelEncoder()
factor_columns = ['state_company', 'city']
model_dataset = bottom_99_dataset.dropna(subset=factor_columns)
model_dataset['state_company'] = le_state.fit_transform(model_dataset['state_company'])
model_dataset['city'] = le_city.fit_transform(model_dataset['city'])

model_columns = ['cnpj',
                 'issue_date_day',
                 'issue_date_month',
                 'issue_date_year']
X = model_dataset[model_columns + factor_columns]
y = model_dataset['total_net_value']
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=0)


# In[24]:

from sklearn.linear_model import LinearRegression

model = LinearRegression(n_jobs=-1)
model.fit(X_train, y_train)
model.score(X_test, y_test)


# In[25]:

import unicodedata

def normalize_string(string):
    if isinstance(string, str):
        nfkd_form = unicodedata.normalize('NFKD', string.lower())
        return nfkd_form.encode('ASCII', 'ignore').decode('utf-8')


# In[26]:

import nltk
from sklearn.feature_extraction.text import CountVectorizer

stopwords = nltk.corpus.stopwords.words('portuguese')
count_vect = CountVectorizer(stop_words=stopwords)
trade_names = dataset.loc[dataset['supplier'].notnull(),
                          'supplier'].unique()
trade_names = np.vectorize(normalize_string)(trade_names)
dataset_counts = count_vect.fit_transform(trade_names)


# In[27]:

frequent_words = sorted(list(zip(count_vect.get_feature_names(),
    np.asarray(dataset_counts.sum(axis=0)).ravel())), key=lambda x: -x[1])


# In[28]:

frequent_words[:20]


# In[29]:

frequent_words = dict(frequent_words)

excluded_keywords = ['ltda', 'cia']
[frequent_words.pop(keyword) for keyword in excluded_keywords]


# In[30]:

def business_type(name):
    fun = np.vectorize(lambda x: normalize_string(x))
    keywords = set(fun(name.split(' '))) - set(stopwords)
    key_freqs = list(map(lambda x: (x, frequent_words.get(x)), list(keywords)))
    key_freqs = [key_freq for key_freq in key_freqs if key_freq[1] is not None]
    if key_freqs:
        key_freq = max(key_freqs, key=lambda x: x[1])
        return key_freq[0]

dataset['supplier_keyword'] = dataset['supplier'].apply(business_type)
bottom_99_dataset['supplier_keyword'] =     bottom_99_dataset['supplier'].apply(business_type)


# In[31]:

le_state = LabelEncoder()
le_city = LabelEncoder()
le_supplier_keyword = LabelEncoder()
factor_columns = ['state_company', 'supplier_keyword']
model_dataset = bottom_99_dataset.dropna(subset=factor_columns)
model_dataset['state_company'] = le_state.fit_transform(model_dataset['state_company'])
model_dataset['city'] = le_city.fit_transform(model_dataset['city'])
model_dataset['supplier_keyword'] = le_city.fit_transform(model_dataset['supplier_keyword'])

model_columns = ['cnpj',
                 'issue_date_day',
                 'issue_date_month',
                 'issue_date_year']
X = model_dataset[model_columns + factor_columns]
y = model_dataset['total_net_value']
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=0)


# In[32]:

model = LinearRegression(n_jobs=-1)
model.fit(X_train, y_train)
model.score(X_test, y_test)


# ## Common CNPJs
# 
# Expenses in the same restaurant are expected to follow a normal distribution. Can we find outliers in companies with enough expenses to analyze?

# In[33]:

from scipy.stats import normaltest

def normaltest_pvalue(values):
    if len(values) >= 20:
        return normaltest(values).pvalue
    else:
        return 1

net_values_by_cnpj = dataset.groupby('cnpj_cpf')['total_net_value']     .agg([len, np.mean, np.std, normaltest_pvalue])     .sort_values('len', ascending=False)     .reset_index()
net_values_by_cnpj['threshold'] = net_values_by_cnpj['mean'] +     3 * net_values_by_cnpj['std']
applicants_per_cnpj = dataset.groupby('cnpj_cpf')['applicant_id']     .aggregate(lambda x: len(set(x))).reset_index()     .rename(columns={'applicant_id': 'congresspeople'})
net_values_by_cnpj = pd.merge(net_values_by_cnpj, applicants_per_cnpj)
net_values_by_cnpj.head()


# In[34]:

len(net_values_by_cnpj.query('normaltest_pvalue < .05')) / len(net_values_by_cnpj)


# In[35]:

data_with_threshold = pd.merge(dataset, net_values_by_cnpj, on='cnpj_cpf')     .sort_values('total_net_value', ascending=False)


# In[36]:

data_with_threshold['main_activity'] =     data_with_threshold['main_activity'].apply(normalize_string)


# In[37]:

is_hotel_reimbursement = data_with_threshold['main_activity']     .str.contains('hoteis').astype(np.bool)
outliers = data_with_threshold[~is_hotel_reimbursement]     .query('(congresspeople > 3) & (len >= 20) & (total_net_value > threshold)')
print(len(outliers), outliers['total_net_value'].sum())


# ## Foursquare

# In[45]:

foursquare = pd.read_csv('../data/2016-12-02-foursquare-companies.xz',
                         low_memory=False)
foursquare.head()


# In[48]:

foursquare.iloc[0]


# In[57]:

print(foursquare['price.tier'].notnull().sum(),
      foursquare['price.tier'].notnull().sum() / len(companies),
      foursquare.query('confirmed_match == True')['price.tier'].notnull().sum() / len(companies))


# In[ ]:



