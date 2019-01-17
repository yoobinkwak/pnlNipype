#!/usr/bin/env python

import nrrd
import numpy as np
import argparse
import warnings
import os
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import nibabel as nib

PRECISION= 17
np.set_printoptions(precision= PRECISION)


def _space2ras(space):
    '''Find the diagonal transform required to transform space to RAS'''

    positive= space.split('-')

    xfrm=[ ]
    if positive[0] is 'left':
        xfrm.append(-1)
    else:
        xfrm.append(1)

    if positive[1] is 'posterior':
        xfrm.append(-1)
    else:
        xfrm.append(1)

    if positive[2] is 'inferior':
        xfrm.append(-1)
    else:
        xfrm.append(1)

    # return 4x4 diagonal matrix
    xfrm.append(1)
    return np.diag(xfrm)



def main():

    parser = argparse.ArgumentParser(description='NRRD to NIFTI conversion tool')
    parser.add_argument('-i', '--input', type=str, required=True, help='input nrrd file')
    parser.add_argument('-p', '--prefix', type=str,
                        help='output prefix for .nii.gz, .bval, and .bvec files (default: input prefix)')


    args = parser.parse_args()
    if args.prefix:
        prefix= os.path.abspath(args.prefix)
    else:
        prefix= os.path.abspath(args.input).split('.')[0]

    img= nrrd.read(args.input)
    hdr= img[1]
    data= img[0]

    SPACE_UNITS = 2
    TIME_UNITS = 0

    SPACE2RAS = _space2ras(hdr['space'])
    xfrm_nhdr= np.matrix(np.vstack((np.hstack((hdr['space directions'][:3,:3].T,
                        np.reshape(hdr['space origin'],(3,1)))),[0,0,0,1])))
    xfrm_nifti= SPACE2RAS @ xfrm_nhdr
    # RAS2IJK= xfrm_nifti.I

    if hdr['dimension']==4:
        axis_elements= hdr['kinds']
        for i in range(4):
            if axis_elements[i] == 'list' or axis_elements[i] == 'vector':
                grad_axis= i
                break

        # put the gradients along last axis
        if grad_axis!=3:
            data= np.moveaxis(data, grad_axis, 3)

        # write .bval and .bvec
        f_val= open(prefix+'.bval', 'w')
        f_vec= open(prefix+'.bvec', 'w')
        b_max = float(hdr['DWMRI_b-value'])

        mf= np.matrix(np.vstack((np.hstack((hdr['measurement frame'],
                                            [[0],[0],[0]])),[0,0,0,1])))
        for ind in range(hdr['sizes'][grad_axis]):
            bvec = [float(num) for num in hdr[f'DWMRI_gradient_{ind:04}'].split()]
            L_2= np.linalg.norm(bvec[:3])
            bval= round(L_2 ** 2 * b_max)

            bvec.append(1)
            # bvecINijk= RAS2IJK @ SPACE2RAS @ mf @ np.matrix(bvec).T
            # simplified below
            bvecINijk= xfrm_nhdr.T @ mf @ np.matrix(bvec).T

            L_2= np.linalg.norm(bvecINijk[:3])
            if L_2:
                bvec_norm= bvecINijk[:3]/L_2
            else:
                bvec_norm= [0, 0, 0]

            f_val.write(str(bval)+' ')
            f_vec.write(('  ').join(str(x) for x in np.array(bvec_norm).flatten())+'\n')

        f_val.close()
        f_vec.close()

        TIME_UNITS= 8


    # automatically sets dim, data_type, pixdim, affine
    img_nifti= nib.nifti1.Nifti1Image(data, affine= xfrm_nifti)
    hdr_nifti= img_nifti.header

    # now set xyzt_units, sform_code= qform_code= 2 (aligned)
    # https://nifti.nimh.nih.gov/nifti-1/documentation/nifti1fields/nifti1fields_pages/xyzt_units.html
    # simplification assuming 'mm' and 'sec'
    hdr_nifti.set_xyzt_units(xyz= SPACE_UNITS, t= TIME_UNITS)
    hdr_nifti['qform_code'] = 2
    hdr_nifti['sform_code']= 2

    hdr_nifti['descrip']= 'pnl-bwh-hms'
    nib.save(img_nifti, prefix+'.nii.gz')



if __name__ == '__main__':
    main()
