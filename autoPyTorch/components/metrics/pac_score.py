import numpy as np
import scipy as sp

from sklearn.utils.multiclass import type_of_target


def pac_metric(solution, prediction):
    """
    Probabilistic Accuracy based on log_loss metric.
    We assume the solution is in {0, 1} and prediction in [0, 1].
    Otherwise, run normalize_array.
    :param solution:
    :param prediction:
    :param task:
    :return:
    """

    def normalize_array(solution, prediction):
        """
        Use min and max of solution as scaling factors to normalize prediction,
        then threshold it to [0, 1].
        Binarize solution to {0, 1}. This allows applying classification
        scores to all cases. In principle, this should not do anything to
        properly formatted classification inputs and outputs.
        :param solution:
        :param prediction:
        :return:
        """
        # Binarize solution
        sol = np.ravel(solution)  # convert to 1-d array
        maxi = np.nanmax(sol[np.isfinite(sol)])
        mini = np.nanmin(sol[np.isfinite(sol)])
        if maxi == mini:
            print('Warning, cannot normalize')
            return [solution, prediction]
        diff = maxi - mini
        mid = (maxi + mini) / 2.

        solution[solution >= mid] = 1
        solution[solution < mid] = 0
        # Normalize and threshold predictions (takes effect only if solution not
        # in {0, 1})

        prediction -= float(mini)
        prediction /= float(diff)

        # and if predictions exceed the bounds [0, 1]
        prediction[prediction > 1] = 1
        prediction[prediction < 0] = 0
        # Make probabilities smoother
        # new_prediction = np.power(new_prediction, (1./10))

        return [solution, prediction]

    def log_loss(solution, prediction, task):
        """Log loss for binary and multiclass."""
        [sample_num, label_num] = solution.shape
        # Lower gives problems with float32!
        eps = 0.00000003

        if (task == 'multiclass') and (label_num > 1):
            # Make sure the lines add up to one for multi-class classification
            norma = np.sum(prediction, axis=1)
            for k in range(sample_num):
                prediction[k, :] /= sp.maximum(norma[k], eps)

            sample_num = solution.shape[0]
            for i in range(sample_num):
                j = np.argmax(solution[i, :])
                solution[i, :] = 0
                solution[i, j] = 1

            solution = solution.astype(np.int32, copy=False)
            # For the base prediction, this solution is ridiculous in the
            # multi-label case

            # Bounding of predictions to avoid log(0),1/0,...
        prediction = sp.minimum(1 - eps, sp.maximum(eps, prediction))
        # Compute the log loss
        pos_class_log_loss = -np.mean(solution * np.log(prediction), axis=0)
        if (task != 'multiclass') or (label_num == 1):
            # The multi-label case is a bunch of binary problems.
            # The second class is the negative class for each column.
            neg_class_log_loss = -np.mean(
                (1 - solution) * np.log(1 - prediction), axis=0)
            log_loss = pos_class_log_loss + neg_class_log_loss
            # Each column is an independent problem, so we average.
            # The probabilities in one line do not add up to one.
            # log_loss = mvmean(log_loss)
            # print('binary {}'.format(log_loss))
            # In the multilabel case, the right thing i to AVERAGE not sum
            # We return all the scores so we can normalize correctly later on
        else:
            # For the multiclass case the probabilities in one line add up one.
            log_loss = pos_class_log_loss
            # We sum the contributions of the columns.
            log_loss = np.sum(log_loss)
            # print('multiclass {}'.format(log_loss))
        return log_loss

    def prior_log_loss(frac_pos, task):
        """Baseline log loss.
        For multiplr classes ot labels return the volues for each column
        """
        eps = 1e-15
        frac_pos_ = sp.maximum(eps, frac_pos)
        if task != 'multiclass':  # binary case
            frac_neg = 1 - frac_pos
            frac_neg_ = sp.maximum(eps, frac_neg)
            pos_class_log_loss_ = -frac_pos * np.log(frac_pos_)
            neg_class_log_loss_ = -frac_neg * np.log(frac_neg_)
            base_log_loss = pos_class_log_loss_ + neg_class_log_loss_
            # base_log_loss = mvmean(base_log_loss)
            # print('binary {}'.format(base_log_loss))
            # In the multilabel case, the right thing i to AVERAGE not sum
            # We return all the scores so we can normalize correctly later on
        else:  # multiclass case
            fp = frac_pos_ / sum(
                frac_pos_
            )  # Need to renormalize the lines in multiclass case
            # Only ONE label is 1 in the multiclass case active for each line
            pos_class_log_loss_ = -frac_pos * np.log(fp)
            base_log_loss = np.sum(pos_class_log_loss_)
        return base_log_loss

    y_type = type_of_target(solution)

    if y_type == 'binary':
        if len(solution.shape) == 1:
            solution = solution.reshape((-1, 1))
        if len(prediction.shape) == 1:
            prediction = prediction.reshape((-1, 1))
        if len(prediction.shape) == 2:
            if prediction.shape[1] > 2:
                raise ValueError('A prediction array with probability values '
                                 'for %d classes is not a binary '
                                 'classification problem' % prediction.shape[1])
            # Prediction will be copied into a new binary array - no copy
            prediction = prediction[:, 1].reshape((-1, 1))
        else:
            raise ValueError('Invalid prediction shape %s' % prediction.shape)

    elif y_type == 'multiclass':
        if len(solution.shape) == 2:
            if solution.shape[1] > 1:
                raise ValueError('Solution array must only contain one class '
                                 'label, but contains %d' % solution.shape[1])
        elif len(solution.shape) == 1:
            pass
        else:
            raise ValueError('Solution.shape %s' % solution.shape)

        # Need to create a multiclass solution and a multiclass predictions
        max_class = int(np.max((np.max(solution), np.max(prediction))))
        solution_binary = np.zeros((len(solution), max_class + 1))
        for i in range(len(solution)):
            solution_binary[i, int(solution[i])] = 1
        solution = solution_binary

    elif y_type == 'multilabel-indicator':
        solution = solution.copy()

    else:
        raise NotImplementedError('pac_score does not support task type %s'
                                  % y_type)

    solution, prediction = normalize_array(solution, prediction.copy())

    sample_num, _ = solution.shape

    eps = 1e-7
    # Compute the base log loss (using the prior probabilities)
    pos_num = 1. * np.sum(solution, axis=0, dtype=float)  # float conversion!
    frac_pos = pos_num / sample_num  # prior proba of positive class
    the_base_log_loss = prior_log_loss(frac_pos, y_type)
    the_log_loss = log_loss(solution, prediction, y_type)

    # Exponentiate to turn into an accuracy-like score.
    # In the multi-label case, we need to average AFTER taking the exp
    # because it is an NL operation
    pac = np.mean(np.exp(the_log_loss * -1))
    base_pac = np.mean(np.exp(the_base_log_loss * -1))
    # Normalize: 0 for random, 1 for perfect
    score = (pac - base_pac) / sp.maximum(eps, (1 - base_pac))

    return score