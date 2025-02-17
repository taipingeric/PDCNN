import math

import numpy as np
import tensorflow as tf
import keras.backend as K


class BBoxUtility(object):
    def __init__(self, num_classes, rpn_pre_boxes = 12000, rpn_nms = 0.7, nms_iou = 0.3, min_k = 300):



        self.num_classes   = num_classes



        self.rpn_pre_boxes = rpn_pre_boxes



        self._min_k        = min_k

        self.boxes  = tf.compat.v1.placeholder(dtype='float32', shape=(None, 4))
        self.scores = tf.compat.v1.placeholder(dtype='float32', shape=(None,))
        
        self.nms_out_rpn        = tf.image.non_max_suppression(self.boxes, self.scores, min_k, iou_threshold=rpn_nms)
        self.nms_out_classifer  = tf.image.non_max_suppression(self.boxes, self.scores, min_k, iou_threshold=nms_iou)
        self.sess               = K.get_session()
        
    def decode_boxes(self, mbox_loc, anchors, variances):

        anchor_width     = anchors[:, 2] - anchors[:, 0]
        anchor_height    = anchors[:, 3] - anchors[:, 1]

        anchor_center_x  = 0.5 * (anchors[:, 2] + anchors[:, 0])
        anchor_center_y  = 0.5 * (anchors[:, 3] + anchors[:, 1])


        detections_center_x = mbox_loc[:, 0] * anchor_width * variances[0]
        detections_center_x += anchor_center_x
        detections_center_y = mbox_loc[:, 1] * anchor_height * variances[1]
        detections_center_y += anchor_center_y
        

        detections_width   = np.exp(mbox_loc[:, 2] * variances[2])
        detections_width   *= anchor_width
        detections_height  = np.exp(mbox_loc[:, 3] * variances[3])
        detections_height  *= anchor_height


        detections_xmin = detections_center_x - 0.5 * detections_width
        detections_ymin = detections_center_y - 0.5 * detections_height
        detections_xmax = detections_center_x + 0.5 * detections_width
        detections_ymax = detections_center_y + 0.5 * detections_height


        detections = np.concatenate((detections_xmin[:, None],
                                      detections_ymin[:, None],
                                      detections_xmax[:, None],
                                      detections_ymax[:, None]), axis=-1)

        detections = np.minimum(np.maximum(detections, 0.0), 1.0)
        return detections

    def detection_out_rpn(self, predictions, anchors, variances = [0.25, 0.25, 0.25, 0.25]):





        mbox_conf   = predictions[0]



        mbox_loc    = predictions[1]

        results = []



        for i in range(len(mbox_loc)):



            detections     = self.decode_boxes(mbox_loc[i], anchors, variances)



            c_confs         = mbox_conf[i, :, 0]
            c_confs_argsort = np.argsort(c_confs)[::-1][:self.rpn_pre_boxes]




            confs_to_process = c_confs[c_confs_argsort]
            boxes_to_process = detections[c_confs_argsort, :]



            idx = self.sess.run(self.nms_out_rpn, feed_dict={self.boxes: boxes_to_process, self.scores: confs_to_process})




            good_boxes  = boxes_to_process[idx]
            results.append(good_boxes)
        return np.array(results)

    def frcnn_correct_boxes(self, box_xy, box_wh, input_shape, image_shape):



        box_yx = box_xy[..., ::-1]
        box_hw = box_wh[..., ::-1]
        input_shape = np.array(input_shape)
        image_shape = np.array(image_shape)

        box_mins    = box_yx - (box_hw / 2.)
        box_maxes   = box_yx + (box_hw / 2.)
        boxes  = np.concatenate([box_mins[..., 0:1], box_mins[..., 1:2], box_maxes[..., 0:1], box_maxes[..., 1:2]], axis=-1)
        boxes *= np.concatenate([image_shape, image_shape], axis=-1)
        return boxes
        
    def detection_out_classifier(self, predictions, rpn_results, image_shape, input_shape, confidence = 0.3, variances = [0.125, 0.125, 0.25, 0.25]):

        Negtiveuse = False



        proposal_conf   = predictions[0]



        proposal_loc    = predictions[1]

        results = []



        for i in range(len(proposal_conf)):
            results.append([])




            detections              = []



            rpn_results[i, :, 2]    = rpn_results[i, :, 2] - rpn_results[i, :, 0]
            rpn_results[i, :, 3]    = rpn_results[i, :, 3] - rpn_results[i, :, 1]
            rpn_results[i, :, 0]    = rpn_results[i, :, 0] + rpn_results[i, :, 2] / 2
            rpn_results[i, :, 1]    = rpn_results[i, :, 1] + rpn_results[i, :, 3] / 2
            for j in range(proposal_conf[i].shape[0]):



                if Negtiveuse:
                    score = np.max(proposal_conf[i][j, :-1])
                    label = np.argmax(proposal_conf[i][j, :-1])
                else:
                    score = np.max(proposal_conf[i][j, :])
                    label = np.argmax(proposal_conf[i][j, :])


                if score < confidence:
                    continue



                x, y, w, h      = rpn_results[i, j, :]
                tx, ty, tw, th  = proposal_loc[i][j, 4 * label: 4 * (label + 1)]

                x1 = tx * variances[0] * w + x
                y1 = ty * variances[1] * h + y
                w1 = math.exp(tw * variances[2]) * w
                h1 = math.exp(th * variances[3]) * h

                xmin    = x1 - w1/2.
                ymin    = y1 - h1/2.
                xmax    = x1 + w1/2
                ymax    = y1 + h1/2

                detections.append([xmin, ymin, xmax, ymax, score, label])

            detections = np.array(detections)
            results[-1].extend(detections)
















            if len(results[-1]) > 0:
                results[-1] = np.array(results[-1])
                box_xy, box_wh = (results[-1][:, 0:2] + results[-1][:, 2:4])/2, results[-1][:, 2:4] - results[-1][:, 0:2]
                results[-1][:, :4] = self.frcnn_correct_boxes(box_xy, box_wh, input_shape, image_shape)

        return results
