from __future__ import division
import numpy as np
from numpy import array, exp, log, dot, abs, multiply, cumsum
from numpy.random import uniform, normal
from scipy.linalg import norm
from numpy import isfinite
from arsenal.terminal import yellow, green, red


def compare(expect, got, name=None):
    """
    Compare vectors.

    TODO:
     - Can plot again eachother

    """
    expect = np.asarray(expect)
    got = np.asarray(got)
    assert expect.shape == got.shape
    [n] = expect.shape

    data = []
    if not isfinite(got).all():
        data.append(['`got` not finite.', '', False])

    if not isfinite(expect).all():
        data.append(['`expect` not finite.', '', False])

    # TODO: add an option to drop NaNs.
    #print expect
    #print got
    #inds = isfinite(expect) & isfinite(got)
    #if not inds.any():
    #    print red % 'TOO MANY NANS'
    #    return
    #expect = expect[inds]
    #got = got[inds]

    c = cosine(expect, got)
    data.append(['cosine-sim', c, (c > 0.99999)])

    # TODO: this check should probably take into account the scale of the data.
    d = linf(expect, got)
    data.append(['Linf', d, d < 1e-10])

    # same sign check (weak agreement, but useful sanity check -- especially for
    # gradients)
    x = expect
    y = got
    s = np.asarray(~((x > 0) ^ (y > 0)), dtype=int)
    p = s.sum() * 100.0 / len(s)
    data.append(['same-sign', '%s%% (%s/%s)' % (p, s.sum(), len(s)), p == 100.0])

    # relative error
    r = np.abs(expect - got) / [max(x,y) for x,y in zip(np.abs(expect), np.abs(got))]
    r = np.mean(r[isfinite(r)])
    data.append(['mean relative error', r, r <= 0.01])

    # TODO: suggest that if relative error is high and rescaled error is low (or
    # something to do wtih regression residuals) that maybe there is a
    # (hopefully) simple fix via scale/offset.

    # TODO: can provide descriptive statistics for each vector
    #data.append(['range (expect)', [expect.min(), expect.max()], 2])
    #data.append(['range (got)   ', [got.min(), got.max()], 2])

    # regression and rescaled error only valid for n >= 2
    if n >= 2:
        # rescaled error
        E = expect / np.abs(expect).max()
        G = got / np.abs(got).max()
        R = np.abs(E - G)
        r = np.mean(R)
        data.append(['mean rescaled error', r, r <= 1e-10])

        # least squares linear regression
        #
        # TODO: for regression we want parameters `[1 0]` and a small
        # residual. We want both these conditions to hold. Might be useful to
        # look at R^2 statistic since it normalizes scale and number of
        # data-points. (it's often used for reduction in variance.)
        #
        from scipy.linalg import lstsq
        A = np.ones((got.shape[0], 2))
        A[:,0] = got
        data.append(['regression', lstsq(A, expect), 2])

    print
    print 'Comparison%s:' % (' (%s)' % name if name else '')
    #print yellow % 'expected:'
    #print expect
    #print yellow % 'got:'
    #print got
    for k, v, passed in data:
        if passed == 1:
            c = green
        elif passed == 0:
            c = red
        else:
            c = yellow
        print '  %s: %s' % (k, c % (v,))
    print

    # TODO: return information computed here as an object or dict.
    return data


def linf(a, b):
    return abs(a - b).max()


def cosine(a, b):
    if not isfinite(a).all() or not isfinite(b).all():
        return np.nan
    A = norm(a)
    B = norm(b)
    if A == 0 and B == 0:
        return 1.0
    elif A != 0 and B != 0:
        return a.dot(b) / A / B
    else:
        return np.nan


class Mixture(object):
    """
    Mixture of several densities
    """
    def __init__(self, w, pdfs):
        w = array(w)
        assert (w >= 0).all() and abs(1 - w.sum()) <= 1e-10, \
            'w is not a prob. distribution.'
        self.pdfs = pdfs
        self.w = w
        self.cdf = np.cumsum(w)

    def rvs(self, size=1):
        # sample component
        i = self.cdf.searchsorted(uniform(size=size))
        # sample from component
        return np.array([self.pdfs[j].rvs() for j in i])

    def pdf(self, x):
        return sum([p.pdf(x) * w for w, p in zip(self.w, self.pdfs)])


def spherical(size):
    "Generate random vector from spherical Gaussian."
    x = normal(0, 1, size=size)
    x /= norm(x, 2)
    return x


def cdf(a):
    """
    Empirical CDF of data `a`, returns function which makes values to their
    cumulative probabilities.

     >>> g = cdf([5, 10, 15])

    Evaluate the CDF at a few points

     >>> g([5,9,13,15,100])
     array([ 0.33333333,  0.33333333,  0.66666667,  1.        ,  1.        ])


    Check that ties are handled correctly

     >>> g = cdf([5, 5, 15])

     The value p(x <= 5) = 2/3

     >>> g([0, 5, 15])
     array([ 0.        ,  0.66666667,  1.        ])

    """

    x = np.array(a, copy=True)
    x.sort()

    def f(z):
        return np.searchsorted(x, z, 'right') * 1.0 / len(x)

    return f


def sample(w, n=None):
    """
    Uses the inverse CDF method to return samples drawn from an (unnormalized)
    discrete distribution.
    """
    c = cumsum(w)
    r = uniform() if n is None else uniform(size=n)
    return c.searchsorted(r * c[-1])


def log_sample(w):
    "Sample from unnormalized log-distribution."
    return sample(exp(w - w.max()))


def cumavg(x):
    """
    Cumulative average.

    >>> cumavg([1,2,3,4,5])
    array([ 1. ,  1.5,  2. ,  2.5,  3. ])

    """
    return np.cumsum(x) / np.arange(1.0, len(x)+1)


def normalize_zscore(data):
    """
    Shift and rescale data to be zero-mean and unit-variance along axis 0.
    """
    shift = data.mean(axis=0)
    rescale = data.std(axis=0)
    rescale[rescale == 0] = 1.0   # avoid divide by zero
    return (data - shift) / rescale


def normalize_interval(data):
    """
    Shift and rescale data so that it lies in the range [0,1].
    """
    shift = data.min(axis=0)
    rescale = data.max(axis=0) - shift
    rescale[rescale == 0] = 1.0  # avoid divide by zero
    return (data - shift) / rescale


def normalize(p):
    return p / p.sum()


def lidstone(p, delta):
    """
    Lidstone smoothing is a generalization of Laplace smoothing.
    """
    return normalize(p + delta)


# based on implementation from scikits-learn
def logsumexp(arr, axis=0):
    """Computes the sum of arr assuming arr is in the log domain.

    Returns log(sum(exp(arr))) while minimizing the possibility of
    over/underflow.

    Examples
    --------

    >>> a = np.arange(10)
    >>> log(sum(exp(a)))
    9.4586297444267107
    >>> logsumexp(a)
    9.4586297444267107
    """
    arr = np.asarray(arr)
    arr = np.rollaxis(arr, axis)
    # Use the max to normalize, as with the log this is what accumulates the
    # less errors
    vmax = arr.max(axis=0)
    out = log(exp(arr - vmax).sum(axis=0))
    out += vmax
    return out


def exp_normalize(x, T=1.0):
    """
    >>> x = [1, -10, 100, .5]
    >>> exp_normalize(x)
    array([  1.01122149e-43,   1.68891188e-48,   1.00000000e+00,
             6.13336839e-44])
    >>> exp(x) / exp(x).sum()
    array([  1.01122149e-43,   1.68891188e-48,   1.00000000e+00,
             6.13336839e-44])
    """
    y = array(x)      # creates copy
    y /= T
    y -= y.max()
    y = exp(y)
    y /= y.sum()
    return y


log_of_2 = log(2)

def entropy(p):
    "Entropy of a discrete random variable with distribution `p`"
    assert len(p.shape) == 1
    p = p[p.nonzero()]
    return -dot(p, log(p)) / log_of_2


def kl_divergence(p, q):
    """ Compute KL divergence of two vectors, K(p || q).
    NOTE: If any value in q is 0.0 then the KL-divergence is infinite.
    """
    return dot(p, log(p) - log(q)) / log_of_2


# KL(p||q) = sum_i p[i] log(p[i] / q[i])
#          = sum_i p[i] (log p[i] - log q[i])
#          = sum_i p[i] log p[i] - sum_i p[i] log(q[i])
#          = Entropy(p) + CrossEntropy(p,q)

# timv: do we need to specify all three things?
#
#  P(x) = sum_y P(x,y) by law of total probabilty
def mutual_information(joint):
    """
    Mutual Information

    MI(x,y) = KL( p(x,y) || p(x) p(y) )

    joint = p(x,y)
    p = p(x)
    q = q(y)

    relationships:
      MI(x,y) is the expected PMI(x,y) wrt p(x,y)
      MI(x,y) = KL( p(x,y) || p(x) p(y) )

    properties:
      MI(X,Y) = MI(Y,X) is symmetric
    """
    # we can compute px and py from joint by applying the law of total probability
    px = joint.sum(axis=1)
    py = joint.sum(axis=0)
    independent = multiply.outer(px, py)
    assert joint.shape == independent.shape
    return kl_divergence(array(joint.flat), array(independent.flat))


def cross_entropy(p, q):
    """ Cross Entropy of two vectors,

    CE(p,q) = - \sum_i p[i] log q[i]

    Relationship to KL-divergence:

      CE(p,q) = entropy(p) + KL(p||q)
    """
    assert len(p) == len(q)
    p = p[p > 0]
    return -dot(p, log(q)) / log_of_2


def assert_isdistr(p):
    assert (p >= 0).all()
    assert (p <= 1).all()
    assert abs(p.sum() - 1.0) < 0.000001


def equal(a, b, tol=1e-10):
    "L_{\inf}(a - b) < tol"
    return inf_norm(a,b) < tol


def inf_norm(a, b):
    return abs(a - b).max()


def assert_equal(a, b, tol=1e-10, name='', verbose=False, throw=True):
    err = inf_norm(a,b)
    if name:
        name = '%s: ' % name
    if verbose or err > tol:
        msg = '%s%s %s err=%s' % (name, a, b, err)
        if throw and err > tol:
            raise AssertionError(msg + ' >= tolerance (%s)' % tol)
        else:
            print msg, green % 'ok' if err < tol else red % 'fail'


if __name__ == '__main__':
    #import doctest; doctest.testmod()

    def tests():

        # Entropy tests
        assert entropy(array((0.5, 0.5))) == 1.0
        assert abs(entropy(array((0.75, 0.25))) - 0.8112781244) < 1e-10
        assert abs(entropy(array((0.1, 0.1, 0.8))) - 0.9219280948) < 1e-10

        # KL-divergence tests
        assert kl_divergence(array((0.5, 0.5)), array((0.5, 0.5))) == 0.0

        # KL, Entropy, and Cross Entropy relationship
        p = array([0.5, 0.5])
        q = array([0.4, 0.6])
        assert_equal(cross_entropy(p, q), (entropy(p) + kl_divergence(p, q)))

        # Normalize tests
        assert_equal(array([0.5, 0.5]), normalize(array([2, 2])))

        # Mutual Information tests
        #Pjoint = array([[0.25, 0.25], [0.25, 0.25]])

        Pjoint = normalize(np.random.rand(4,10))
        assert_equal(mutual_information(Pjoint),
                     mutual_information(Pjoint.T))

        def mi_independent_is_zero(px, py):
            assert_equal(mutual_information(multiply.outer(px, py)), 0.0)

        mi_independent_is_zero(p, q)
        mi_independent_is_zero(array([0.1, 0.1, 0.2, 0.6]),   # non-square joint
                               array([0.9, 0.1]))


        print 'passed tests.'

    tests()
