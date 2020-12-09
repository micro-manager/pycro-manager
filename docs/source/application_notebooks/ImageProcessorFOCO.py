import numpy as np
import cv2
from numba import jit


class ImageProcessor:
    def __init__(self, ops=None):

        if ops is None:
            ops = build_ops()

        # store ops
        self.ops = ops

        # helper fxn to initialize a template filter for
        self.template_filter = gaussian_2d(
            1 + 6 * self.ops["template_filter_width"], self.ops["template_filter_width"]
        )

    def set_ops(self, ops):
        """ helper wrapper to change imageprocessor params"""

        self.ops = ops

    def segmentchunk(self, frame):

        # image preprocessing
        filt_frame = image_filtering(
            frame,
            self.ops["fb_post_threshold"],
            self.ops["fb_threshold_margin"],
            self.ops["med_filt_size" ""],
            self.template_filter,
        )

        # find blobs
        # print('Finding centers...')
        xs, ys = find_centers(filt_frame, self.ops["fb_threshold_margin"])

        if len(xs) == 0:
            return []

        # merge blobs
        # print('Merging centers...')
        xs, ys = merge_centers(xs, ys, self.ops["fb_min_blob_spacing"])

        return list(zip(xs, ys))


def image_filtering(
    frame,
    fb_post_threshold=50,
    fb_threshold_margin=50,
    med_filt_size=5,
    template_filter=None,
):
    """
    :param frame:
    :param args:
    :return:
    """

    # apply threshold
    threshold = np.median(frame) + fb_threshold_margin
    frame = (frame > threshold) * frame

    # apply median filter
    frame = cv2.medianBlur(frame, med_filt_size)

    # template filtering
    frame = cv2.matchTemplate(frame, template_filter, cv2.TM_CCOEFF)

    # pad frame b/c of template matching
    p = (len(template_filter) // 2) + 1
    frame = np.pad(frame, (p, 0), "constant")

    return (frame > fb_post_threshold) * frame


@jit(nopython=True)
def find_centers(frame, fb_threshold_margin):

    # skipping edge pixels
    sd = frame.shape
    edg = 3
    [x, y] = np.where(frame[edg : sd[0] - edg, edg : sd[1] - edg - 1])

    # initialize outputs
    # cent = []
    # cent_map = np.zeros(sd)
    x = x + edg - 1
    y = y + edg - 1
    # links_x = []
    # links_y = []
    # links_hi = []
    # links_vi = []
    xs = [0]
    ys = [0]

    # federatedcenters_ind = []
    # federatedcentermap = np.zeros(sd)

    for j in range(0, len(y)):
        if (
            (frame[x[j], y[j]] >= frame[x[j] - 1, y[j] - 1])
            and (frame[x[j], y[j]] >= frame[x[j] - 1, y[j]])
            and (frame[x[j], y[j]] >= frame[x[j] - 1, y[j] + 1])
            and (frame[x[j], y[j]] >= frame[x[j], y[j] - 1])
            and (frame[x[j], y[j]] >= frame[x[j], y[j] + 1])
            and (frame[x[j], y[j]] >= frame[x[j] + 1, y[j] - 1])
            and (frame[x[j], y[j]] >= frame[x[j] + 1, y[j]])
            and (frame[x[j], y[j]] >= frame[x[j] + 1, y[j] + 1])
        ):

            # cent.append([x[j], y[j]])
            # cent_map[x[j], y[j]] = cent_map[x[j], y[j]] + 1

            # ridge/mesa consolidation code
            # find horizontal neighbor pixels of equal value
            if frame[x[j], y[j]] == frame[x[j] - 1, y[j]]:

                pass
                # links_hi.append(j)
                # federatedcentermap[x[j], y[j]] = federatedcentermap[x[j] - 1, y[j]]

            # find horizontal neighbor pixels of equal value
            elif frame[x[j], y[j]] == frame[x[j], y[j] - 1]:

                pass
                # links_vi.append(j)
                # federatedcentermap[x[j], y[j]] = federatedcentermap[x[j], y[j] - 1]

            else:

                # federatedcenters['ind'].append(sub2ind(frame.shape, x[j], y[j]))
                # federatedcentermap[x[j], y[j]] = sub2ind(frame.shape, x[j], y[j])
                # print('x: {}; y: {}'.format(x[j], y[j]))
                # print('ravel: {}'.format(np.ravel_multi_index((x[j], y[j]), frame.shape, mode='raise',order='C')))
                # federatedcenters_ind.append(np.ravel_multi_index((x[j], y[j]), frame.shape, mode='raise', order='C'))
                # federatedcentermap[x[j], y[j]] = 10000
                xs.append(x[j])
                ys.append(y[j])

    return xs[1:], ys[1:]


@jit(nopython=True)
def merge_centers(xs, ys, fb_min_blob_spacing):
    """

    :param xs:
    :param ys:
    :return:
    """

    # grab number of centers
    numcenters = len(xs)

    # code for removing rois
    code = 9999

    if numcenters != 0:

        # calculate distance between all centers
        # set all values to dummy high values and greedy alg search for min
        dist_matrix = np.ones((numcenters, numcenters)) * 200

        # calculate distances
        for n in range(numcenters):
            for n2 in range(n + 1, numcenters):

                # calculate distance
                dist = np.sqrt(((xs[n] - xs[n2]) ** 2) + ((ys[n] - ys[n2]) ** 2))

                # add to distance matrix
                dist_matrix[n, n2] = dist

        # greedy alg remove minimum distance till we're small enough
        mindist = np.amin(dist_matrix)
        while mindist < fb_min_blob_spacing:

            # get min distance and min pixel pair
            mindist = np.amin(dist_matrix)
            minpixelpair = np.argmin(dist_matrix)

            # fit linear ndx to larger ndx
            # [c1, c2] = np.unravel_index(minpixelpair, (numcenters, numcenters), order='C')
            # c1, c2 = ind2sub([numcenters, numcenters], minpixelpair)
            # c1 = minpixelpair // numcenters
            c2 = minpixelpair % numcenters

            # kill c2
            xs[c2] = code
            ys[c2] = code

            # remove acccording to code in matrix
            dist_matrix[:, c2] = code
            dist_matrix[c2, :] = code

    # remove entries with code
    xs = [x for x in xs if x != code]
    ys = [y for y in ys if y != code]

    return xs, ys


@jit(nopython=True)
def gaussian_2d(im_width, sigma):
    """

    :param im_width:
    :param sigma:
    :return:
    """

    g = np.zeros((im_width, im_width), dtype=np.float32)

    # gaussian filter
    for i in range(int(-(im_width - 1) / 2), int((im_width + 1) / 2)):
        for j in range(int(-(im_width - 1) / 2), int((im_width + 1) / 2)):
            x0 = int((im_width) / 2)  # center
            y0 = int((im_width) / 2)  # center
            x = i + x0  # row
            y = j + y0  # col
            g[y, x] = np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / 2 / sigma / sigma)
            # g[x, y] = np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / 2 / sigma / sigma)

    return g


def build_ops():

    # quant params
    fb_threshold_margin = 40
    fb_min_blob_spacing = 8
    fb_post_threshold = 40
    cb_maxdist = 9
    template_filter_width = 3
    med_filt_size = 5

    ops = {
        "fb_threshold_margin": fb_threshold_margin,
        "fb_min_blob_spacing": fb_min_blob_spacing,
        "fb_post_threshold": fb_post_threshold,
        "cd_maxdist": cb_maxdist,
        "template_filter_width": template_filter_width,
        "med_filt_size": med_filt_size,
    }

    return ops
