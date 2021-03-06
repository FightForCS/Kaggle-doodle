import os
os.environ['CUDA_VISIBLE_DEVICES'] = '4,5,6,7'  #'4,5,6,7'#'0,1,2,3' #'3,2,1,0'

from common import *
from data   import *



##----------------------------------------
from model32_se_resnext50 import *




def test_augment(drawing,label,index, augment):
    cache = Struct(data = drawing.copy(), label = label, index=index)

    #<todo> ... different test-time augment ...
    # if augment=='drop':
    #     # drop TTA, randomly drop 10% strokes, line or points
    #     # but I have not use training augmentation, will that work?
    #     drop_line = False
    #     if drop_line:
    #         n = len(drawing)
    #         num_to_drop = int(n*0.1)
    #         idx = list(range(n))
    #         random.shuffle(idx)
    #         drop_idx = set(idx[:num_to_drop])
    #         drawing = [drawing[i] for i in range(n) if i not in drop_idx]
    #     else:
    #         for i in range(len(drawing)):
    #             x = drawing[i][0]
    #             y = drawing[i][1]
    #             n = len(x)
    #             num_to_drop = int(n*0.1)
    #             idx = list(range(n))
    #             random.shuffle(idx)
    #             drop_idx = set(idx[:num_to_drop])
    #             x = [x[i] for i in range(n) if i not in drop_idx]
    #             y = [y[i] for i in range(n) if i not in drop_idx]
    #             drawing[i] = [x,y]
    #
    #     pass


    image = drawing_to_image(drawing, 256, 256)

    if augment=='flip':
        image = cv2.flip(image, 1)





    return image, label, cache




##############################################################################################

#generate prediction npy_file
def make_npy_file_from_model(checkpoint, mode, split, augment, out_test_dir, npy_file):

    ## setup  -----------------
    # os.makedirs(out_test_dir +'/backup', exist_ok=True)
    # backup_project_as_zip(PROJECT_PATH, out_dir +'/backup/code.test.%s.zip'%IDENTIFIER)

    log = Logger()
    log.open(out_test_dir +'/log.submit.txt',mode='a')
    log.write('\n--- [START %s] %s\n\n' % (IDENTIFIER, '-' * 64))
    log.write('\tSEED         = %u\n' % SEED)
    log.write('\tPROJECT_PATH = %s\n' % PROJECT_PATH)
    log.write('\tout_test_dir = %s\n' % out_test_dir)
    log.write('\n')


    ## dataset ----------------------------------------
    log.write('** dataset setting **\n')
    batch_size     = 256*4 #256 #512

    test_dataset = DoodleDataset(mode, split,
                              lambda drawing, label, index : test_augment(drawing, label, index, augment),)
    test_loader  = DataLoader(
                        test_dataset,
                        sampler     = SequentialSampler(test_dataset),
                        batch_size  = batch_size,
                        drop_last   = False,
                        num_workers = 2,
                        pin_memory  = True,
                        collate_fn  = null_collate)

    assert(len(test_dataset)>=batch_size)
    log.write('test_dataset : \n%s\n'%(test_dataset))
    log.write('\n')


    ## net ----------------------------------------
    log.write('** net setting **\n')
    net = Net().cuda()

    log.write('%s\n\n'%(type(net)))
    log.write('\n')


    if 1:
        log.write('\tcheckpoint = %s\n' % checkpoint)
        net.load_state_dict(torch.load(checkpoint, map_location=lambda storage, loc: storage))


        ####### start here ##########################
        criterion = softmax_cross_entropy_criterion
        test_num  = 0
        probs    = []
        truths   = []
        losses   = []
        corrects = []

        net.set_mode('test')
        for input, truth, cache in tqdm(test_loader):
            print('\r\t',test_num, end='', flush=True)
            test_num += len(truth)
#             if test_num>1000*batch_size: break

            with torch.no_grad():
                input = input.cuda()
                logit = data_parallel(net,input)
                prob  = F.softmax(logit,1)
                probs.append(prob.data.cpu().numpy())
            # prob = prob.data.cpu().numpy()
            # truth = truth.data.cpu().numpy()
            # probs.append(prob[range(prob.shape[0]),truth])

#                 if mode=='train': # debug only
#                     truth = truth.cuda()
#                     loss    = criterion(logit, truth, False)
#                     correct = metric(logit, truth, False)

#                     losses.append(loss.data.cpu().numpy())
#                     corrects.append(correct.data.cpu().numpy())
#                     truths.append(truth.data.cpu().numpy())


        assert(test_num == len(test_loader.sampler))
        print('\r\t',test_num, end='\n', flush=True)
        prob = np.concatenate(probs)

#         if mode=='train': # debug only
#             correct = np.concatenate(corrects)
#             truth   = np.concatenate(truths).astype(np.int32).reshape(-1,1)
#             loss    = np.concatenate(losses)
#             loss    = loss.mean()
#             correct = correct.mean(0)
#             top = [correct[0], correct[0]+correct[1], correct[0]+correct[1]+correct[2]]
#             precision = correct[0]/1 + correct[1]/2 + correct[2]/3
#             print('top      ', top)
#             print('precision', precision)
#             print('')
    #-------------------------------------------


    np.save(npy_file, np_float32_to_uint8(prob))
    print(prob.shape)
    log.write('\n')






def prob_to_csv(prob, key_id, csv_file):
    top = np.argsort(-prob,1)[:,:3]
    word = []
    for (t0,t1,t2) in top:
        word.append(
            CLASS_NAME[t0] + ' ' + \
            CLASS_NAME[t1] + ' ' + \
            CLASS_NAME[t2]
        )
    df = pd.DataFrame({ 'key_id' : key_id , 'word' : word}).astype(str)
    df.to_csv(csv_file, index=False, columns=['key_id', 'word'])



def npy_file_to_sbmit_csv(mode, split, npy_file, csv_file):
    print('NUM_CLASS', NUM_CLASS)
    complexity='simplified'

    if mode=='train':
        raise NotImplementedError

    if mode=='test':
        assert(NUM_CLASS==340)
        global TEST_DF

        if TEST_DF == []:
            TEST_DF = pd.read_csv(DATA_DIR + '/csv/test_%s.csv'%(complexity))
        key_id = TEST_DF['key_id'].values


    prob = np_uint8_to_float32(np.load(npy_file))
    print(prob.shape)

    prob_to_csv(prob, key_id, csv_file)
















#################################################################################################3

def run_test_fold():

    balance = torch.load(open('/datanew/DATASET/doodle/results/2018-12-1/test/ori2.pkl', "rb"))


    TEST_DF = pd.read_csv(DATA_DIR + '/csv/test_simplified.csv')
    key_id = TEST_DF['key_id'].values


    prob = balance.cpu().numpy()
    print(prob.shape)

    prob_to_csv(prob, key_id, 'balance.csv')







# main #################################################################
if __name__ == '__main__':
    print( '%s: calling main function ... ' % os.path.basename(__file__))

    run_test_fold()


    print('\nsucess!')


