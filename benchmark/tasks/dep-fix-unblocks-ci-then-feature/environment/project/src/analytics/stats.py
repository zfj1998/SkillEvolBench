from scipy import zscore, pearsonr

def compute_statistics(values):
    z = zscore(values)
    return {"z_scores": [round(v, 4) for v in z], "count": len(values)}

def compute_correlation(x, y):
    return round(pearsonr(x, y), 4)
