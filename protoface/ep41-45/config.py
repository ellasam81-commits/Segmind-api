"""Approved initial clips only; accepted episode/parts are excluded."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
AAD_PREFIX="ep41-45"
REMOTE_ROOT="protoface/ep41-45"
MODEL="minimax/minimax-h3"
PARTS=tuple(range(1,13))
PARTS_BY_EPISODE={44: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), 45: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)}
EPISODES=tuple(sorted(PARTS_BY_EPISODE))
INITIAL_CLIP_COUNT=24
INITIAL_CREDITS=192
ALREADY_ACCEPTED_PARTS=((41, 1), (41, 2), (41, 3), (41, 4), (41, 5), (41, 6), (41, 7), (41, 8), (41, 9), (41, 10), (41, 11), (41, 12), (42, 1), (42, 2), (42, 3), (42, 4), (42, 5), (42, 6), (42, 7), (42, 8), (42, 9), (42, 10), (42, 11), (42, 12), (43, 1), (43, 2), (43, 3), (43, 4), (43, 5), (43, 6), (43, 7), (43, 8), (43, 9), (43, 10), (43, 11), (43, 12))
TOTAL_APPROVED_CREDITS=480
MAX_PARALLEL_INITIAL_REQUESTS=3
AUTHORIZED_INPUT_SHA256={'44:1': '048fb86b2cdb20e0ffc713177e81e0bb2789808e09a1508cf8c159f265f4c555', '44:2': '56fc427607e2408f50bf1c621171dea4044a60af38a625d41f1eaf39f41ddba2', '44:3': '1caaad7f7def30720445ba92ea914c1e5664b79ded846d54c0f8388fe071546d', '44:4': '0edb3f4325d84eadb4a3e2d246acd175fd61c88da5de4b4547366f5f12856342', '44:5': '8fd11efc2253591d06785f16b860367ddfb8100082b8857709c3300355ead84b', '44:6': 'fa428668e513d88685d1477a9de2209741fadbebad445c69bd6c415559231420', '44:7': '75f86de52ca6e1b086fda0f06e3a913a0c50453295815583f7e6e46b90332698', '44:8': 'df451abd476431b429d1e7bddefaee111cab7e55b44dfedd94d33cc416fffbcb', '44:9': '599b069e64631749e5213bc55a37586ac6644f11bc6508d924e3507484e5e733', '44:10': '77a9176535f26650d3e83c98c4f5607557718373b01b9d9022df5f00f93afee9', '44:11': 'f6377771522c0b1996c1d6d195faebe61b334cba40a2a0750fa19a0190536a43', '44:12': 'e6ca47c5f81a93978457db80493ea1c72371944408510c58e0fdf897fb045d69', '45:1': '9d338e3def5fab5165bd78f808a275a185c8e0bee733618983349e59459065ca', '45:2': '62a0841b8fda3d21b482fb1e87e10fb1fe1ad5fdadffdee8b3f22dc91d28dc91', '45:3': '246bc35d26800d6ed772839791e21f7ed43c1154da49db8b3d63d867d4c0637b', '45:4': '27853bb7092f1f40f48111b09af365915571d330552050df5af69fc4303102e5', '45:5': '1c66d7d2dba38660bcef2257641f475e05863a839f25bc6c4445f37903413e19', '45:6': 'c8d51dd734decab01722b0ae0403e5ced277389261d0cb849a76dbc77fd2f241', '45:7': 'a986c4dd3a6a2444477fce653e6f91df37953a873392a0978202fc2ce4bff8da', '45:8': '1021dd693ddeda5e6aa6f11d2f476abcb38567904fcc3d3048b3a6de78c65c03', '45:9': 'ac46c651a6ee0240f0fbc42c3e1d5841325b9d49abaf661ba4289a6b9b60bca4', '45:10': '399942361a30b47562a85cd09b4f87d513f95406b5aa194cdffb39e36dc2263e', '45:11': 'eb4d7c294dd72c0718c94b7e55781e412fca6b24f001820b1f29017642d470c2', '45:12': '59ce498915de2f090e217cb78724b80442d30daa7613145d4637e71b922bebca'}
def parts_for(episode):
    if episode not in PARTS_BY_EPISODE: raise ValueError('Episode has no approved unsubmitted parts')
    return PARTS_BY_EPISODE[episode]
LOCAL_RETURN_PRIVATE_KEY=Path(os.environ.get("TD_RETURN_PRIVATE_KEY","/workspace/thirteen-doors/next-batch-41-45/transport-private/return-private.pem"))
