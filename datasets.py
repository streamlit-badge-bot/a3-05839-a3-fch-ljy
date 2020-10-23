import openml

def mnist():
    mnist = openml.datasets.get_dataset('mnist_784')
    x, y, categorical, attribute_names = mnist.get_data()
    feats = x.drop('class', axis='columns').to_numpy().astype('float32')
    labels = x['class'].to_numpy()
    return feats, labels